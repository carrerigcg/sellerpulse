# SellerPulse

Analytics para vendedores do Mercado Livre. **Está em produção, com conta real
conectada e dados reais de faturamento.** Não é protótipo: o que quebra aqui
quebra para alguém.

O vendedor conecta a conta pelo OAuth oficial do ML, a ingestão traz seis meses
de pedidos, e o produto responde o que a plataforma não responde: quanto sobra
de cada venda, quais produtos sustentam a loja, quem são os compradores que
valem reconquistar, e quais anúncios são vistos sem converter.

## Arquitetura

| Camada | Onde | O quê |
| --- | --- | --- |
| Front | `frontend/` | Next.js 16 (App Router), Tailwind, na Vercel |
| API | `backend/` | FastAPI + asyncpg, no Render |
| Banco | Supabase | Postgres 17, RLS em todas as tabelas |
| Worker | `backend/worker/` | drena `sync_jobs` no mesmo processo da API |
| MCP | `backend/mcp_server.py` | seis ferramentas somente leitura sobre a demo |

`src/` é o código original do projeto. **Não está morto**: `ml_client`,
`storage`, `auth`, `session_auth` e `demo_data` são dependência viva do backend,
e `metrics`/`segmentation` são a referência de paridade que os testes do
`backend/analytics/` comparam contra. Aquela camada está congelada — mexer nela
é uma mudança diferente e mais arriscada.

## Convenções

- **Specs em `docs/specs/`**, nunca em `docs/superpowers/specs/`. Uma spec por
  feature, com as decisões travadas e o porquê.
- **Commits em português**, estilo conventional (`feat(escopo): ...`). A
  mensagem explica o **porquê**, não o que o diff já mostra.
- **Comentários explicam a razão**, não a mecânica. Se um comentário puder ser
  deduzido do código ao lado, ele é ruído.
- **Fluxo de merge:** mudança só de front-end vai direto para `main`. Back-end,
  banco e migrations passam por PR com CI verde.

## Armadilhas que já custaram caro

Cada uma destas quebrou de verdade. A lista existe para não quebrarem de novo.

**Nunca inventar número.** Um `COST_ESTIMATE_RATE` de 55% chutava o custo do
produto e virava "lucro" na tela. Foi removido: custo de produto só entra se o
vendedor informar. A mesma regra vale para qualquer limiar — benchmark sai do
dado do próprio vendedor (mediana da loja), não de constante.

**Ausência não é zero.** Custo não informado, visita não colhida e conversão sem
amostra aparecem como `—`, nunca `0`. Zero é uma afirmação, e quem somar a
coluna vai acreditar nela.

**O seletor "Até" é exclusivo.** Escolher 13/10 devolve dados até 12/10. Está
decidido e documentado na aba Exportar; ao conferir números contra o ML, somar
um dia.

**O dia é o do vendedor, não UTC.** `FUSO_DO_VENDEDOR` em
`backend/analytics/_common.py`. Agrupar em UTC movia 14% dos pedidos para o dia
seguinte.

**Função não atravessa a fronteira RSC.** Props de Server para Client Component
são dado puro. O erro aparece em tempo de execução com `lint` e `build`
passando, porque as rotas do dashboard são dinâmicas (`ƒ`) e nunca são
renderizadas no build. **Abrir a página no navegador é parte da verificação, não
um extra.**

**O banco de teste nasce completo; produção não.** `setup_test_db.py`
reconstrói o schema a cada CI, então toda migration nova está lá — e nenhum
teste vê a diferença para produção. Uma feature já foi mergeada com o código
consultando uma tabela que não existia em produção. Daí
`backend/migrations/APLICADAS.tsv` e a trava `checa_migrations.py` na CI:
migration no repo que não esteja registrada como aplicada deixa o PR vermelho.

**Toda tabela de tenant ganha policy de RLS.** `item_visits` nasceu sem, e o
papel `anon` — a chave pública do front-end — tinha até `TRUNCATE` sobre ela.
Ao criar tabela nova, comparar com o schema ao lado, não só com a spec.

**O worker é opt-out.** `WORKER_IN_PROCESS` tem default `"1"`. Subir o backend
local com o `backend/.env` liga o worker contra a Supabase de **produção**. Para
verificar algo localmente, apontar `DATABASE_URL` para o banco de teste e
desligar o worker explicitamente.

**`data/demo.db` é byte-determinístico.** Para dar dado novo à demonstração,
derivar no seeding do Postgres (`backend/seed.py`), não mexer no gerador — o
RNG é consumido em sequência e pedir um número a mais desloca todos os preços
seguintes, sem nada falhar.

## Rodando

Dois ambientes virtuais, de propósito: a raiz tem o pacote legado, o
`backend/` tem o SaaS.

```bash
# backend (Windows: Scripts/ no lugar de bin/)
backend/.venv/Scripts/python.exe -m pytest backend/tests -q

# suite legada
.venv/Scripts/python.exe -m pytest -q

# frontend
cd frontend && npm test && npm run lint && npm run build
```

Os testes do backend precisam de Postgres em
`postgresql://postgres:postgres@localhost:5432/sellerpulse_test`.
`python backend/scripts/setup_test_db.py --recreate` prepara o schema.

## Verificação

**Teste que não falha quando o código quebra não é teste.** O padrão aqui é
quebrar de propósito, confirmar que o teste cai, e restaurar.

E **confirmar que a mutação foi aplicada** antes de ler o resultado — um `sed`
que não casou, ou uma escrita que falhou, produz "tudo passou" que não significa
nada. Isso já aconteceu três vezes; o `diff` antes do `pytest` é o que pega.

## Contato

Guilherme Carreri — [carreri.gcg@gmail.com](mailto:carreri.gcg@gmail.com)
