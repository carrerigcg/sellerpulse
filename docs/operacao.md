# Operação do SellerPulse

O "como fazer" que o `AGENTS.md` só aponta. Ler a seção que interessa, não o
arquivo inteiro.

## 1. Rodar localmente sem tocar em produção

O `backend/.env` aponta para a Supabase de **produção**, e o worker sobe
**ligado** por padrão (`WORKER_IN_PROCESS`, default `"1"`). Subir o backend com
esse arquivo drena a fila real e escreve na base real. Os dois flags parecem
simétricos e não são: `DEMO_REFRESH_IN_PROCESS` é opt-in e, se ligado,
regenera a demo publicada.

O caminho seguro já está pronto em `.claude/launch.json`:

- **`backend-teste`**: aponta para `sellerpulse_test`, desliga o worker e o
  refresh da demo e fixa o seller de demonstração
  `11111111-2222-3333-4444-555555555555`, na porta 10000.
- **`frontend`**: o dev server na porta 3000. O `frontend/.env.local` precisa
  de `NEXT_PUBLIC_API_URL=http://localhost:10000`.

O banco de teste é um Postgres 17 local (`postgres:postgres@localhost:5432`).
`setup_test_db.py` cria o banco `sellerpulse_test` se faltar, e o
`--recreate` refaz o schema do zero. O `psql` não está no PATH, e não precisa:
o script usa asyncpg.

**Para ver a demo com dados**, crie o seller e semeie, sempre conferindo o
banco antes de escrever:

```python
# backend/.venv/Scripts/python.exe - < este trecho
import asyncio, uuid, asyncpg
from datetime import datetime, UTC
from backend.seed import seed_postgres
DEMO = uuid.UUID("11111111-2222-3333-4444-555555555555")
USER = uuid.UUID("11111111-2222-3333-4444-666666666666")
async def main():
    pool = await asyncpg.create_pool(
        "postgresql://postgres:postgres@localhost:5432/sellerpulse_test",
        server_settings={"timezone": "UTC"})
    async with pool.acquire() as c:
        assert await c.fetchval("select current_database()") == "sellerpulse_test"
        await c.execute("insert into auth.users(id,email) values($1,'demo@exemplo.test') on conflict do nothing", USER)
        await c.execute("insert into sellers(id,user_id,is_demo) values($1,$2,true) on conflict do nothing", DEMO, USER)
    print(await seed_postgres(pool, DEMO, anchor=datetime.now(UTC)))
    await pool.close()
asyncio.run(main())
```

No fim, apague o seller (`delete from sellers where id = ... and is_demo`; o
cascade leva o resto) e o usuário em `auth.users`.

## 2. Verificar uma tela

- **Abrir a página é obrigatório.** As rotas do dashboard e da demo são
  dinâmicas (`ƒ`), e o build nunca as renderiza. Erro de fronteira RSC só
  aparece com a página aberta.
- **Use a sua própria aba** (`tabs_create`), nunca a que o Guilherme está
  olhando. Aba em segundo plano não renderiza quadros: o `close` do `<dialog>`
  não dispara nela, e isso parece defeito sem ser.
- **Cache de fetch do Next:** `lib/demo.ts` guarda as respostas por 1 hora,
  em `.next/dev/cache/fetch-cache` e na memória do dev server. Depois de mudar
  o backend ou o banco, pare o `frontend`, apague essa pasta e suba de novo.
  Sem isso, a tela mostra o dado de antes e você investiga um defeito que não
  existe.
- Os erros de WebSocket do HMR no console são ruído do dev server.

## 3. Teste de mutação sem perder trabalho

1. Copie o arquivo para fora do repo (`cp arquivo "$TEMP/x.bak"`).
2. Aplique a quebra. Prefira a ferramenta Edit; com `sed`, confira depois.
3. **Confirme que a quebra foi aplicada** com
   `diff --strip-trailing-cr "$TEMP/x.bak" arquivo`. A árvore é CRLF: sem o
   `--strip-trailing-cr`, um `sed -i` aparece como o arquivo inteiro mudado, e
   você não sabe se a mutação pegou.
4. Rode só o teste que deveria cair, e leia o motivo da falha. Ele precisa ser
   o teste daquela regra, e a falha precisa ser de asserção. Uma mutação que
   quebra o próprio código (um parâmetro SQL que fica sem uso, um `import`
   fora de lugar) derruba vários testes por **erro**, e isso parece "pegou"
   sem provar nada. Aconteceu duas vezes em 2026-10-28.
5. Restaure **da cópia** e confira com `diff -q`.

**Nunca restaure com `git checkout -- arquivo`:** isso volta ao último commit
e apaga junto o conserto que ainda não foi commitado. Já aconteceu.

Script que procura texto dentro de arquivo (Node `includes`, Python `in`)
precisa normalizar `\r\n` antes. Se o texto não casar, o script deve falhar
**antes** de escrever.

## 4. Migration em produção

A ordem não muda:

1. Escreva a migration. Se ela cria tabela de tenant, escreva a policy de RLS
   **num arquivo separado e logo em seguida**, porque o banco de teste não
   tem `auth.uid()` (ver `0011` e `0013`).
2. Acrescente-a em `MIGRATIONS` no `backend/scripts/setup_test_db.py`, se
   ela rodar no banco de teste.
3. Abra o PR. O CI fica vermelho na trava `checa_migrations.py`, e isso é o
   esperado.
4. Com o ok do Guilherme, confira em produção o que a migration assume (nome
   de constraint, coluna que ainda não existe) e aplique as duas em sequência.
5. Confira o resultado (RLS ligada, contagens) e registre no `APLICADAS.tsv` a
   `version` que o Supabase gravou.
6. Push, CI verde, merge.

Entre o passo 4 e o deploy, o código velho roda sobre o schema novo. Pense no
que ele grava nessa janela. Exemplo: a `0012` precisou que a coleta de frete
preenchesse `shipment_id` de pedidos ingeridos pelo código velho.

## 5. Depois do merge: conferir que subiu

O auto-deploy já falhou em silêncio nas **duas** plataformas: o Render no
PR #18 e a Vercel no PR #20.

- **Render** (`srv-dar79erncjis73cdjf9g`): `list_deploys` precisa mostrar o
  commit do merge como `live`. Se não aparecer, `trigger_deploy`.
- **Vercel**: confira por um marcador que **só a versão nova** tem (um texto
  novo, uma coluna nova da API), nunca por "deu 200 e o título está certo".
  Se não subiu, `create_deployment` a partir do último deploy de produção
  bom, com `withLatestCommit`.
- O backend do plano free hiberna. A primeira chamada pode levar ~25 s.

## 6. Produção: ler é livre, escrever pede ok

- SQL **de leitura** no Supabase de produção pode ser rodado à vontade para
  medir e auditar.
- Escrita (migration, update, fila, variável de ambiente) só com o ok do
  Guilherme. Na ferramenta do Render, `update_environment_variables` **mescla**
  as variáveis; nunca use `replace: true`.
- **Token do ML:** uma consulta só de leitura à API do ML com o token da conta
  real precisa de ok, deve abrir o banco em modo somente leitura
  (`default_transaction_read_only`) e **aborta se o token estiver perto de
  vencer**. Renovar fora do backend troca o refresh token sem gravar o novo, e
  a conta desconecta.

## 7. Sincronização

- A sincronização diária fica em `.github/workflows/sincronizacao-agendada.yml`.
- A cadeia de jobs por vendedor é **delta → visitas → frete**: cada um
  enfileira o próximo depois de terminar, porque o índice único só admite um
  job ativo por vendedor.
- Visitas e frete fazem uma chamada ao ML por item e por envio,
  respectivamente. Por isso renovam o lease a cada passo.
- `last_synced_at` é a marca d'água dos **pedidos**. Só o delta e o backfill a
  atualizam.

## 8. Guarda e verificação

**`scripts/verifica.py`** é o "rodei e passou" do agente. No modo rápido
(sem argumento), ele olha o que mudou desde a `origin/main` e roda só o que a
mudança pode quebrar:

- ruff;
- a trava de migrations;
- a bateria do guarda;
- os arquivos de teste do backend que citam o `.py` alterado;
- vitest, eslint e tsc no front.

Quando um `.py` do backend muda e nenhum teste o cita, ele avisa em vez de
fingir que testou. `--completo` reproduz o CI inteiro.

**`.claude/hooks/guarda.mjs`** é um hook `PreToolUse`, configurado no
`.claude/settings.json`. Ele nega três coisas:

1. Editar migration registrada no `APLICADAS.tsv`.
2. Subir o backend sem banco de teste e sem `WORKER_IN_PROCESS=0`, ou usar a
   config `backend` no `preview_start`.
3. Push forçado, ou `git checkout --` / `git restore` / `git reset --hard`
   sobre mudança não commitada.

Quando ele nega, a mensagem já diz o que fazer no lugar. **Siga a
alternativa.** Não contorne o guarda nem o desligue sem o ok do Guilherme.
Se o próprio guarda falhar (JSON inesperado, por exemplo), ele **libera e
avisa**: um guarda com bug não pode parar o trabalho em silêncio.

Ao mexer no guarda, rode `node .claude/hooks/testa_guarda.mjs`. O
`verifica.py` e o CI também rodam essa bateria. Ela testa caminhos nos três
formatos que chegam no Windows (`C:\`, `C:/` e o `/c/` do Git Bash), porque o
primeiro bug do guarda foi uma comparação de pasta que não casava e liberava
a edição da migration. Os casos ficam num arquivo, e não na linha de comando,
porque o Git Bash reescreve as barras invertidas nos argumentos.

Configuração nova de hook só vale numa sessão nova, ou quando o Claude Code
recarrega o `.claude/settings.json`.
