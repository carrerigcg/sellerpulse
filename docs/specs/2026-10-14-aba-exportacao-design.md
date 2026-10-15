# Aba Exportar — tutorial e glossário de colunas

Data: 2026-10-14
Estado: implementado em 2026-10-14 (`224c297`, direto na main por ser so front-end).

## Por quê

A exportação em CSV entrou em 2026-10-13 (`28d65b8`) como um botão no cabeçalho
de cada seção. Funciona, e é invisível: quem não sabe que existe não acha, e
quem acha recebe um arquivo com 19 colunas cujos nomes não se explicam.
`receita_acumulada_pct` e `f_score` são nomes de coluna de banco.

Falta também um lugar onde duas regras do produto estejam escritas. Nenhuma das
duas está documentada em nenhuma tela hoje, e as duas fazem o leitor errar a
conta sozinho:

1. O seletor **"Até" é exclusivo**. Selecionar 13/10 devolve pedidos até 12/10.
   O nome do arquivo diz `_2026-10-13.csv` e o conteúdo para um dia antes.
   (Decidido em 2026-10-01; não é para consertar, é para documentar.)
2. A **recência conta a partir do fim da janela**, não de hoje
   (`segmentation_pg.py:218` usa `date_to` como referência). Com "Até 12/10",
   `recency_dias = 3` significa última compra em 09/10.

## Escopo

Uma aba nova em cada uma das duas árvores:

- `/dashboard/exportar` — dado real do vendedor conectado
- `/demo/exportar` — dado do vendedor sintético da demonstração

O `/demo` não tem exportação nenhuma hoje: o botão ficou só nas três telas
autenticadas. Esta aba fecha essa lacuna, e o `/demo` é o que se abre sem criar
conta.

## Layout

Um cartão por tabela, três ao todo, cada um com seu próprio botão de baixar —
mais um botão "baixar tudo" acima deles, que baixa os três arquivos.

```
Exportar
[ Baixar as três tabelas ]            <- botão de ação, laranja
[Fluxo financeiro] [Produtos] [Clientes]   <- três cartões, botão cada
--------------------------------------------
Como exportar          <- tutorial, 3 passos
Glossário das colunas  <- um bloco por tabela
```

O "baixar tudo" dispara três downloads em sequência. Na primeira vez o Chrome
pede permissão de "downloads múltiplos"; é uma vez por site. Se incomodar, a
alternativa é empacotar em `.zip`, ao custo de uma dependência nova no
navegador — fora do escopo até que se prove necessário.

## Componentes

| Arquivo | Papel |
| --- | --- |
| `components/analytics/painel-exportacao.tsx` | cartões + "baixar tudo". Client Component. |
| `components/analytics/glossario-colunas.tsx` | tutorial + glossário. Server Component, texto estático. |
| `lib/glossario.ts` | o texto do glossário, uma entrada por coluna. |
| `app/dashboard/exportar/page.tsx` | busca com `lib/api.ts` |
| `app/demo/exportar/page.tsx` | busca com `lib/demo.ts` |

As duas páginas são finas: buscam as três tabelas, passam para os mesmos
componentes. É o padrão que `components/analytics/` já usa — os gráficos e
tabelas são compartilhados entre as duas árvores desde a Sprint 3.

Reusa sem alterar: `lib/csv.ts`, `lib/colunas-export.ts`,
`components/analytics/export-button.tsx`. Os tipos (`FluxoDia`, `AbcLinha`,
`RfmLinha`) vêm de `lib/api.ts` e o `lib/demo.ts` importa os mesmos, então
`COLUNAS_*` serve às duas árvores sem ramificação.

### Fronteira RSC

`painel-exportacao.tsx` é `"use client"` porque precisa de `onClick`. As
definições de coluna atravessam como **dado puro** — `Coluna.campo` é
`keyof T`, nunca função. Essa restrição já está documentada em `lib/csv.ts` e
custou uma página quebrada neste projeto, com `lint` e `build` passando.

O glossário é Server Component: texto estático não precisa de JavaScript no
cliente.

## Nome do arquivo

`sellerpulse-<tela>-<de>_<ate>.csv` continua como está no `lib/csv.ts`. Na
demonstração entra `demo` na posição da tela: `sellerpulse-demo-clientes-….csv`.
O conteúdo é de um vendedor sintético, e o servidor MCP já carrega esse aviso
(`AVISO_DEMO`).

A ressalva **não** vai dentro do CSV: uma linha acima do cabeçalho desloca
todas as colunas no Excel.

## Glossário — profundidade

Cada entrada diz **o que a coluna é e como é calculada**. Nada sobre o que
fazer com o número.

É a mesma intenção já travada para os relatórios: guia educativo, regra
genérica, sem opinião de negócio. "Margem abaixo de 15% é ruim" seria palpite
sobre um negócio que não conheço, e cada vendedor tem margem-alvo diferente.

### Conteúdo verificado na fonte

Fluxo financeiro (5 colunas, `metrics_pg.py:180`):

- `margem_contribuicao = receita_bruta − taxas_ml − frete`, arredondado a 2
  casas. **Não desconta custo do produto** — o produto não conhece esse custo
  até o vendedor informar (decisão de 2026-10-01).

Produtos (6 colunas, `segmentation_pg.py:157`):

- Classes pela regra **80/15/5** sobre a receita acumulada: A até 80%, B até
  95%, C o resto. `_classify` compara com `<=`, então o produto que empurra a
  acumulada além de 80% já é B — a fronteira fica logo antes dele. O docstring
  de `segmentation_pg.py` diz "incluído na classe superior", o que induz ao
  erro oposto; o código é que manda.

Clientes (8 colunas, `src/segmentation.py`):

- `frequency` = contagem de pedidos pagos na janela, não de produtos distintos.
- `monetary` = soma de `total_amount`, arredondada a 2 casas.
- `recency_dias` = `date_to` menos a última compra. Como `date_to` é exclusivo,
  quem comprou no último dia incluído aparece com 1, não 0.
- Scores 1–5 por quintil sobre os **valores distintos** observados. Com menos
  de 5 valores distintos o número de faixas cai e o topo não chega a 5 — foi
  exatamente o que zerou os cartões de Clientes na demo em 2026-10-12.
- Segmentos por regras ordenadas, primeira que casar vence: Champions
  (r≥4, f≥4, m≥4), Loyal (f≥4, m≥3), At Risk (r≤2 e (f≥3 ou m≥3)), New
  (r≥4, f≤2), Hibernating (r≤2, f≤2, m≤2), Others para o resto.

## Navegação

Entra em `components/nav/itens.ts`, nos dois grupos. No dashboard vai em
"Análises", depois de Clientes — é uma ação sobre as análises, não configuração
de conta. Sem ícone novo: o `IconeExportar` que entrou com o botão em
`components/nav/icones.tsx` é a seta de download e serve aos dois usos.

## Testes

`lib/csv.ts` já tem 16 testes e não muda. O que entra de novo é texto estático
e composição de componentes — `lint` e `build` cobrem o que há para cobrir
automaticamente aqui.

Verificação manual obrigatória, porque é onde este projeto já se queimou:

1. Abrir as duas rotas no navegador. `lint` e `build` passam com página
   quebrada: as rotas do dashboard são dinâmicas (`ƒ`) e nunca são
   renderizadas no build.
2. Baixar um arquivo de cada tabela e **abrir no Excel**, conferindo acentuação
   e vírgula decimal.
3. Conferir que o nome do arquivo da demo leva `demo`.
4. Conferir a janela: com "Até" em uma data, a última linha do fluxo é do dia
   anterior.

## Fora de escopo

- `.zip` no "baixar tudo"
- Escolher colunas antes de exportar
- Exportar o cohort de produtos (é matriz, não tabela plana — outro formato)
- Agendar exportação ou enviar por e-mail
