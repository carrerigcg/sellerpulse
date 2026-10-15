# SellerPulse — Servidor MCP (fase 1: demonstração)

**Data:** 2026-10-13
**Status:** Implementado em 2026-10-13 (PR #8). Fase 1 no ar; a fase 2 (OAuth) esta adiada por decisao registrada.

---

## 1. Contexto

A JoomPulse — concorrente direto no mesmo marketplace, com planos de R$ 332 a R$ 664/mês — lançou em 2026 um conector MCP e fez dele a manchete do site: *"primeiro conector MCP oficial do Brasil"*, com mais de 3.000 vendedores conectados. O conector inteiro deles é uma URL (`https://joompulse.com/mcp`) mais um login.

O MCP é um protocolo aberto e documentado pela Anthropic. Não há nada de proprietário no mecanismo: o que dá valor ao conector da JoomPulse é o **dado** por trás dele — a base de mercado raspada do Mercado Livre e da Shopee inteiros.

**É exatamente aí que o SellerPulse tem uma resposta que eles não têm.** O MCP da JoomPulse não sabe quanto o vendedor faturou, qual a margem real depois da comissão, quais produtos sustentam a receita ou quais clientes pararam de comprar — porque eles não têm os pedidos daquela conta. O SellerPulse tem.

O trabalho é pequeno porque a parte difícil já está feita: as cinco funções analíticas existem, estão testadas e rodam em produção desde a Sprint 1. O servidor MCP é uma casca nova sobre elas.

## 2. Goals & non-goals

### Goals

- Servidor MCP remoto em `/mcp`, montado no app FastAPI que já existe.
- **Seis ferramentas** sobre a loja de demonstração: cinco análises mais uma visão geral.
- **Sem autenticação nesta fase.** Qualquer pessoa com a URL conecta e explora o dado fictício.
- Todas as respostas **declaram que o dado é de demonstração**.
- Testes no padrão de `backend/tests/`, e merge por PR com CI verde.

### Non-goals

- **OAuth e dado real do vendedor** — é a fase 2. Ver seção 8.
- **Limite de uso, cota, revogação de token.** Sem usuário pagante, seriam requisitos inventados.
- **Ferramentas de escrita.** O MCP só lê. Nada de criar anúncio, alterar preço ou disparar sincronização.
- **Dado de mercado** (categorias, palavras-chave, concorrentes). Exigiria raspar o Mercado Livre inteiro — outro produto.
- **Serviço separado.** Monta no app que já existe; nada de infraestrutura nova.

## 3. Decisões travadas

Decididas com o Guilherme em 2026-10-13. Não re-litigar na implementação.

1. **Demonstração primeiro, login depois.** Entrega algo demonstrável em dias e deixa o caminho do produto aberto.
2. **Seis ferramentas, não cinco nem duas.** As cinco análises mapeadas uma a uma, mais `visao_geral`. A IA começa pelo resumo e desce no detalhe — o que evita cinco chamadas (e cinco acordadas do Render) para responder "como vai meu negócio".
3. **Só leitura.**
4. **Montado no FastAPI existente**, mesmo serviço e mesmo pool.

## 4. Arquitetura

```
Claude.ai / ChatGPT
        │  HTTP (streamable)
        ▼
https://sellerpulse-049j.onrender.com/mcp
        │
        ├── backend/mcp_server.py      ← novo: as 6 ferramentas
        │
        └── backend/analytics/          ← existente, intocado
            ├── metrics_pg.py           fluxo_financeiro, top_produtos
            └── segmentation_pg.py      abc_pareto, rfm_scores, cohort_produto
```

**Dependência nova:** `mcp>=2.3,<3` em `backend/requirements.txt`.

**Montagem** (`backend/main.py`): o SDK expõe `streamable_http_app()`, que devolve um ASGI montável. Três regras não óbvias, todas verificadas na documentação do SDK:

- **O lifespan do app pai tem que abrir o gerenciador de sessão do MCP.** É a linha que todo mundo esquece; sem ela o servidor sobe e não responde. O `lifespan` de `main.py` já existe e vai passar a abrir os dois contextos.
- **O `mount` vem depois das rotas próprias.** Um mount casa com todo caminho abaixo dele; o que vier depois fica inalcançável.
- **A proteção contra DNS-rebinding vem ligada**, e por padrão só responde a `localhost`. Sem declarar as origens permitidas, funciona na máquina do Guilherme e falha no Render. A origem de produção entra na configuração de transporte.

**Identidade do vendedor:** reusa `_seller_de_demo()` de `backend/routers/demo.py`, que lê o `seller_id` de variável de ambiente no servidor. O `seller_id` **nunca** vem como parâmetro de ferramenta — é a mesma regra que protege os endpoints `/demo/*` hoje, e vale igual aqui.

## 5. As seis ferramentas

| Ferramenta | Pergunta que responde | Função por trás |
|---|---|---|
| `visao_geral` | "Como foi o período?" Receita bruta, custo do Mercado Livre, margem de contribuição, e a variação contra o período anterior de mesmo tamanho | `fluxo_financeiro`, agregado |
| `fluxo_financeiro` | Faturamento dia a dia | `fluxo_financeiro` |
| `top_produtos` | Os N produtos que mais faturaram | `top_produtos` |
| `curva_abc` | Quais produtos sustentam a receita (classes A, B, C) | `abc_pareto` |
| `segmentos_de_clientes` | Quem compra de novo e quem sumiu — Campeões, Fiéis, Em risco, Hibernando (RFM) | `rfm_scores` |
| `cohort_de_produtos` | Produto novo vende e some, ou continua faturando? Agrupa produtos pelo mês da primeira venda e segue a receita de cada grupo ao longo dos meses | `cohort_produto` |

> **Atenção ao nome.** `cohort_produto` é cohort de **produtos**, não de clientes: cada linha é um grupo de produtos que teve a primeira venda no mesmo mês, e os valores são receita, não contagem de compradores. Quem responde "o cliente voltou a comprar" é o RFM, pela frequência. Chamar essa ferramenta de "retenção de clientes" faria a IA responder a pergunta errada com números que parecem certos.

**Margem é de contribuição, não lucro.** Receita menos comissão do Mercado Livre menos frete. O custo do produto não entra porque o SellerPulse não o conhece — e a descrição da ferramenta diz isso, senão a IA vai chamar de "lucro".

### Parâmetros

Todas aceitam `date_from` e `date_to` opcionais. **Omitidos, usam os últimos 90 dias.** Sem padrão, a IA inventa datas.

**O `date_to` é exclusivo** no sistema (decisão travada em 2026-10-01). A ferramenta soma um dia internamente antes de chamar a análise, senão toda resposta perde o último dia. Isso é um teste, não um comentário.

### Formato da resposta

JSON, com um envelope fixo:

```json
{
  "aviso": "Dados de demonstração fictícios, não uma loja real.",
  "periodo": { "de": "2026-07-15", "ate": "2026-10-13" },
  "dados": { }
}
```

O campo `aviso` não é decorativo: sem ele a IA apresenta "R$ 331.551" como faturamento real de alguém. É a mesma função da faixa amarela no painel.

## 6. Armadilhas conhecidas

**O Render hiberna.** Plano gratuito, dorme depois de ~15 minutos, e o retorno leva ~23 s. A primeira pergunta de cada sessão vai demorar. Não tem conserto neste plano — a descrição do servidor declara isso, para a IA aguardar em vez de concluir que caiu.

**O conector sem login existe, mas é opção de interface.** No Claude, a etapa de autenticação tem "No sign in". Há relato de que conectores gerenciados por organização assumem OAuth sempre; para uso pessoal, não afeta.

**O nome da classe mudou entre versões do SDK.** Documentação recente importa `MCPServer` de `mcp.server`; exemplos antigos usam `FastMCP`. Conferir o que a 2.3.0 instalada expõe antes de escrever — não copiar de exemplo da internet.

**Usar streamable HTTP, não SSE.** O SDK trata SSE como transporte superado.

## 7. Testes

No padrão de `backend/tests/`, com `pytest-asyncio` e o banco de teste.

- **Uma por ferramenta:** chama e confere a forma da resposta e o envelope.
- **Data padrão:** sem `date_from`/`date_to`, o período é de 90 dias.
- **O dia que faltava:** um pedido no último dia da janela **aparece** no resultado. É o teste que prova que o `date_to` exclusivo foi tratado. Vale confirmar que ele quebra sem o ajuste.
- **O aviso não some:** toda ferramenta devolve `aviso`. Quebrar de propósito e ver o teste falhar.
- **O `seller_id` não é parâmetro:** nenhuma ferramenta aceita `seller_id` na assinatura. É o teste que trava o isolamento.
- **O app sobe com o MCP montado:** as rotas que já existem continuam respondendo depois do mount.

## 8. Fase 2 — fora deste escopo

Registrado para não ser re-descoberto, não para ser construído agora.

Para o vendedor ver o **próprio** dado, o servidor precisa saber quem está perguntando. O caminho natural é OAuth 2.1 com o Supabase, que já emite os JWT que `backend/deps.py` valida. As ferramentas passariam a resolver o `seller_id` pelo `sub` do token, exatamente como `get_current_seller_id` faz hoje — a lógica de isolamento não muda, só a origem da identidade.

Isso traz junto: emissão e revogação de token, limite de uso por conta, e a decisão de quais ferramentas um vendedor pode usar. Nada disso vale projetar antes de existir o primeiro usuário.

## 9. Checkpoints

1. Dependência adicionada e servidor montado; o app sobe e as rotas antigas continuam de pé.
2. As seis ferramentas respondendo localmente, com o envelope e o padrão de data.
3. Testes passando, incluindo o do dia que faltava e o do aviso.
4. PR com CI verde.
5. Depois do merge: conectar no Claude pela URL de produção e fazer três perguntas reais de ponta a ponta.
