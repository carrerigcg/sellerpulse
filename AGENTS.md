# SellerPulse — mapa para agentes

Analytics para vendedores do Mercado Livre. **Está em produção, com conta real
conectada e dados reais de faturamento.** O que quebra aqui quebra para alguém.

O vendedor conecta a conta pelo OAuth do ML, a ingestão traz seis meses de
pedidos, e o produto responde o que a plataforma não responde: quanto sobra de
cada venda, quais produtos sustentam a loja, quem vale reconquistar e quais
anúncios são vistos sem converter. Este arquivo é o mapa; o detalhe
operacional está em `docs/operacao.md`.

## Mapa

| Camada | Onde | O quê |
| --- | --- | --- |
| Front | `frontend/` | Next.js 16 (App Router), Tailwind, na Vercel. Regras do Next em `frontend/AGENTS.md` |
| API | `backend/` | FastAPI + asyncpg, no Render |
| Banco | Supabase | Postgres 17, RLS em todas as tabelas, migrations em `backend/migrations/` |
| Worker | `backend/worker/` | drena `sync_jobs` no mesmo processo da API: delta → visitas → frete |
| MCP | `backend/mcp_server.py` | seis ferramentas somente leitura sobre a demo |
| Legado | `src/` | **vivo e congelado**: `ml_client`, `storage`, `auth`, `session_auth`, `demo_data` são dependência do backend; `metrics`/`segmentation` são a referência de paridade dos testes de `backend/analytics/`. Mexer ali é outra mudança, mais arriscada |

## Comandos

Tudo a partir da raiz. Duas venvs de propósito (raiz = legado, `backend/` =
SaaS), chamadas pelo caminho, nunca ativadas (Linux: `bin/` em vez de `Scripts/`).

```bash
# banco de teste (Postgres local em postgres:postgres@localhost:5432)
backend/.venv/Scripts/python.exe backend/scripts/setup_test_db.py --recreate

# backend: rode os arquivos de teste que a mudança toca
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_<area>.py -q
backend/.venv/Scripts/python.exe -m ruff check backend
backend/.venv/Scripts/python.exe -m ruff format --check backend

# legado
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src tests

# frontend
cd frontend && npm test && npm run lint && npm run build
```

**Antes de dizer "pronto":** `backend/.venv/Scripts/python.exe scripts/verifica.py`
roda só o que a mudança toca (lint, migrations, testes da área); `--completo` é
o CI inteiro. A **suíte completa do backend** fica com o CI ou com o Guilherme.
Tela rodando: configs `backend-teste` e `frontend` do `.claude/launch.json`.

## O que o CI exige (`.github/workflows/tests.yml`)

Três jobs:

1. **test**, em Linux e Windows: ruff check e format em `src tests`, depois
   pytest legado.
2. **backend**: ruff em `backend` e `scripts`, `checa_migrations.py` (toda
   migration no `APLICADAS.tsv`), `setup_test_db.py` e `pytest backend/tests`.
3. **frontend**: `npm ci`, lint, vitest e build (o build inclui os tipos).

## Onde está o estado

Não existe arquivo de progresso. O estado é derivado:

- **Em produção:** o que está na `main`. A Vercel e o Render publicam a partir
  dela, mas o auto-deploy já falhou em silêncio. Conferir antes de afirmar.
- **Em andamento:** `gh pr list` e as branches abertas.
- **Decidido, o porquê e o que falta:** `docs/specs/`. Cada spec tem estado no
  topo, atualizado no merge, e lista o que ficou de fora.
- **`docs/plans/` é local**, nunca versionado, e as caixinhas `- [ ]` de lá
  nunca foram marcadas. Contar caixinha dá a resposta errada.

## Convenções

- **Specs em `docs/specs/`**, uma por feature, com as decisões travadas e o
  porquê. Nunca em `docs/superpowers/specs/`.
- **Commits em português**, no estilo conventional (`feat(escopo): ...`). A
  mensagem explica o **porquê**, não o que o diff mostra.
- **Comentário explica a razão**, não a mecânica.
- **Merge:**
  - mudança só de front-end vai direto para a `main`, com lint e build locais;
  - back-end, `src/`, workflows, migrations e mudanças no harness (`.claude/`,
    hooks) passam por PR com CI verde;
  - PR entra por **squash**.

## Definição de pronto

Uma tarefa só está pronta com evidência, nunca com "parece certo":

1. **Teste que falha quando o código quebra.** Quebre de propósito, confirme
   que a quebra foi aplicada (`diff`) **antes** de ler o resultado, veja o
   teste cair e restaure a partir de uma **cópia**.
2. **`scripts/verifica.py` verde**: lint, format, migrations e testes da área.
3. **Tela aberta no navegador**, se a mudança aparece numa tela. Lint e build
   não renderizam rota dinâmica.
4. **Migration**: aplicada em produção e registrada no `APLICADAS.tsv`
   **antes** do merge. Tabela de tenant nova já nasce com policy de RLS.
5. **Depois do merge**: commit conferido no ar no Render e na Vercel (`verificador-de-entrega`).
6. **No relato e no PR**: o que foi provado e como. E o que não foi.

## Armadilhas que já custaram caro

Cada uma quebrou de verdade (versão longa em `docs/operacao.md`). Três são
barradas por hook, `.claude/hooks/guarda.mjs`: migration aplicada, backend
contra produção e descarte de trabalho não commitado.

- **Nunca inventar número.** Um custo estimado de 55% virou "lucro" na tela.
  Custo só entra se o vendedor informar. Referência sai do dado da própria
  loja (mediana), nunca de constante.
- **Ausência não é zero.** Custo não informado, visita não colhida e frete não
  buscado aparecem como `—` ou como cobertura parcial, nunca como `0`. Zero é
  uma afirmação.
- **O seletor "Até" é exclusivo.** 13/10 devolve até 12/10. Ao conferir contra
  o ML, some um dia.
- **O dia é o do vendedor, não UTC** (`FUSO_DO_VENDEDOR`). Em UTC, 14% dos
  pedidos mudavam de dia.
- **Função não atravessa a fronteira RSC.** O erro só aparece em tempo de
  execução, com lint e build passando.
- **O banco de teste nasce completo; produção não.** Daí o `APLICADAS.tsv` e a
  trava no CI.
- **O worker é opt-out.** `WORKER_IN_PROCESS` vem como `"1"`, e o
  `backend/.env` aponta para a Supabase de **produção**. Subir o backend com
  ele escreve na base real.
- **`data/demo.db` é byte-determinístico.** Dado novo para a demo se deriva no
  `backend/seed.py`. Mexer no gerador desloca todos os preços sem nada falhar.
- **Carrinho é um envio e um `pack_id` para vários pedidos.** Somar frete ou
  contar compras por pedido infla os números.
- **Restaurar mutação com `git checkout --` apaga o trabalho não commitado.**
  Restaure a partir de uma cópia.
- **CRLF:** a árvore de trabalho é CRLF. `sed -i` reescreve o fim de linha, e
  `includes()` de um texto com `\n` não casa. Use a ferramenta Edit, ou
  `diff --strip-trailing-cr`.
- **Cache de fetch do Next na verificação local** (`.next/dev/cache`): a demo
  guarda as respostas por 1 hora. Depois de mudar o backend, pare o dev
  server, apague o cache e suba de novo.

## Trabalhando com o Guilherme

- **Português do Brasil.** Ele decide rápido. Dê opções numeradas, com a sua
  recomendação e o porquê, em texto, e não em widget de pergunta.
- **Não clique nem navegue na aba do navegador que ele está olhando.** Teste
  em aba própria.
- **Antes de escrever em produção** (banco, env, fila, ML), peça o ok dele.
  Leitura é livre.
- **Credencial colada na conversa não é usada.**

## Agentes

Revisores e verificadores em `.claude/agents/` (o "quando usar" está no
`README.md` de lá). Quem gera não julga: revisão é de contexto limpo.
