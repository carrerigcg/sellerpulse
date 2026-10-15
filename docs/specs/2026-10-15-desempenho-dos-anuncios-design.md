# SellerPulse — Seção Desempenho dos anúncios

Data: 2026-10-15
Estado: desenho aprovado, implementação a seguir

## 1. Por quê

Em 2026-10-15 a tela Produtos ganhou Unidades, Visitas e Conversão como
colunas da tabela ABC. Elas entregam **números**. A pergunta que o vendedor
tem é "o que eu faço segunda-feira?", e quem responde isso não é o número: é
a **comparação**.

A spec de visitas já tinha a tese escrita:

> "O primeiro tem um problema de anúncio — preço, foto, título. O segundo tem
> um problema de tráfego."

Isso é um 2×2 — visitas (alta/baixa) × conversão (alta/baixa) —, e a varredura
de referências de 2026-10-15 confirmou a leitura. O relatório de jornada de
conversão do próprio Mercado Livre separa visitas de intenção de compra; as
extensões Lexos Seller Analytics e Hunter Spy vendem exatamente visitas,
vendas e conversão por anúncio. E a orientação recorrente é que **taxa
saudável varia por categoria** — ou seja, limiar fixo é errado.

## 2. A seção, e por que ela não é mais colunas

Uma seção própria abaixo do cohort de lançamento, e as três colunas **saem da
tabela ABC**.

Não é organização: é correção. `receita_acumulada_pct` e a classe A/B/C são
propriedades da ordem por receita — a curva de Pareto. Ordenar aquela tabela
por conversão deixa a coluna de acumulado sem sentido de leitura (os valores
continuam certos por produto, mas param de crescer de cima para baixo) e a
classe sem a ordem que a produziu.

Com duas tabelas, cada uma tem a sua ordem natural: a ABC é sobre **receita** e
continua ordenada por ela; a nova é sobre o **funil** e pode ser ordenada por
qualquer coluna sem quebrar nada.

Custo aceito: olhando a curva ABC não se vê mais conversão ao lado da classe.
Quem quiser cruzar as duas rola até a seção de baixo.

## 3. O diagnóstico

|                              | Conversão **abaixo** da mediana | Conversão **acima** |
| ---------------------------- | ------------------------------- | ------------------- |
| **Visitas acima da mediana** | Visto e rejeitado               | Campeão             |
| **Visitas abaixo**           | Cauda                           | Converte, falta ser visto |

- **Visto e rejeitado** — a ação é no anúncio: preço, foto, título, frete.
- **Converte, falta ser visto** — o anúncio funciona; falta visibilidade. É o
  quadrante mais valioso, porque é dinheiro parado em algo que já está pronto.
- **Campeão** — proteger estoque.
- **Cauda** — candidato a encerrar.

**"Precisam de atenção" = vermelho + azul.** São os dois únicos onde mexer
paga. Campeão e cauda não pedem ação.

### As réguas saem do próprio dado

Mediana da conversão e mediana das visitas **da loja**, calculadas sobre os
produtos diagnosticáveis da janela. Nunca constante.

É a mesma regra do custo de produto, e pela mesma cicatriz: o
`COST_ESTIMATE_RATE` de 55% foi removido em outubro porque número inventado
some dentro de uma conta e vira verdade. A pesquisa reforça — taxa saudável
varia por categoria, então qualquer "abaixo de 1% é ruim" seria chute.

**Mediana e não média:** um item barato de alta recompra (no dado real, um
óleo com 26% de conversão) puxaria a média e faria metade do catálogo parecer
ruim.

## 4. As três travas de honestidade

Esta seção classifica produtos. Classificar errado é pior que não classificar,
porque o rótulo é lido como conclusão.

1. **Número pequeno não vira diagnóstico.** Um produto só é classificado se,
   na conversão mediana da loja, devesse ter tido ao menos **duas** vendas —
   `visitas × mediana_de_conversão >= 2`. Com 8 visitas e mediana de 4,8%, o
   esperado eram 0,4 vendas: não dá para concluir nada. Recebe
   **"poucas visitas para avaliar"**.

   Sem isto, um item com 3 visitas e 1 venda marca 33% e lidera qualquer
   ordenação por conversão. O dado real já tem casos assim.

   **Por que duas e não uma** — e aqui o desenho original estava errado, o que
   só apareceu ao medir a loja real. Nesta população todo produto vendeu ao
   menos uma vez (a lista sai de `order_items`), então a conversão MÍNIMA
   possível é `1/visitas`: pouca visita implica conversão alta por aritmética,
   não por mérito. Com o limiar em uma venda esperada, o produto na fronteira
   converte praticamente na mediana e o quadrante "cauda" fica vazio.

   Medido em 2026-10-15, 431 produtos da loja real:

   | vendas esperadas | diagnosticáveis | rejeitado | campeão | falta ser visto | cauda |
   | --- | --- | --- | --- | --- | --- |
   | 1 | 229 | 94 | 39 | 96 | **0** |
   | 2 | 91 | 36 | 13 | 33 | 9 |
   | 3 | 59 | 18 | 12 | 18 | 11 |

   A mediana de conversão cai de 9,09% para 4,84% entre 1 e 2: os 9% eram
   inflação de amostra pequena, não a conversão da loja. Três seria ainda mais
   seguro e diagnosticaria só 59 dos 431; dois é onde os quatro quadrantes
   existem e ainda sobra catálogo para olhar.

   Tentei antes corrigir com limite inferior de Wilson, que é a ferramenta
   padrão para ordenar taxas com amostras desiguais. **Não resolve**: Wilson
   puxa a taxa pequena para baixo, mas não quebra a anti-correlação mecânica
   entre visitas e conversão nesta população. Medido: a cauda continuou em 0.

2. **Ausência não é zero.** Produto sem visita colhida recebe
   **"sem visita colhida"**, estado distinto de "poucas visitas". Um é falta
   de medição, o outro é medição insuficiente. Mesma regra do custo.

3. **Mediana de poucos produtos não é mediana.** Com menos de 5 produtos
   diagnosticáveis, a mediana é praticamente o valor de um deles. Abaixo
   disso a tabela aparece inteira, **sem rótulos**, dizendo por quê.

   É guarda de exibição, não regra de negócio — daí o número redondo. O que
   ela protege é o leitor de um quadrante que não significa nada.

## 5. Ordenação e filtro

**Cabeçalho clicável**, não menu de opções: clica em Conversão, ordena
crescente; clica de novo, decrescente. Menos interface e mais descoberto que
um seletor com doze combinações.

Colunas ordenáveis: Produto, Visitas, Unidades, Conversão, Diagnóstico.

**Ordem padrão: visitas decrescente.** Não conversão crescente, embora fosse
tentador — produto com 1 visita e 1 venda daria 100%. Mais visto primeiro é
onde um problema de conversão custa mais dinheiro.

**Filtro por diagnóstico**, em chips de seleção única, com a contagem de cada
um. "Todos" é o padrão.

Tudo no navegador, sobre o dado que a página já carregou: nenhum endpoint
novo, nenhuma chamada a mais, resposta instantânea. São 49 produtos na demo e
431 na loja real medida.

## 6. O resumo no topo

Quatro números: conversão mediana da loja, visitas no período, **que fatia do
tráfego vai para anúncio que converte abaixo da mediana**, e quantos estão sem
visita colhida.

O terceiro era "produtos que precisam de atenção", e aquele número era oco:
com corte na mediana, cada quadrante fica com ~25% POR CONSTRUÇÃO, então
"atenção" daria ~50% em qualquer loja, sempre. Dizia respeito ao método, não
ao negócio de quem lê — mesma família do custo estimado.

A fatia de tráfego varia de verdade entre lojas, e é medida de magnitude e não
de contagem: três produtos ruins com dez mil visitas importam mais que vinte
com cinquenta.

A mediana repete embaixo de cada linha da coluna Conversão. Número de
conversão sozinho não diz se é bom — 3% é ótimo em eletrônico e ruim em
acessório.

## 7. Arquivos

| Arquivo | Papel |
| --- | --- |
| `frontend/lib/diagnostico.ts` | medianas, classificação, as três travas. Função pura. |
| `frontend/lib/diagnostico.test.ts` | vitest |
| `frontend/components/analytics/desempenho-anuncios.tsx` | resumo, chips, tabela ordenável. Client Component. |
| `frontend/components/analytics/abc-table.tsx` | **remove** Unidades, Visitas e Conversão |
| `frontend/app/dashboard/produtos/page.tsx` | renderiza a seção abaixo do cohort |
| `frontend/app/demo/produtos/page.tsx` | idem |

A lógica fica separada do componente pelo mesmo motivo do `lib/csv.ts`: é onde
o erro seria silencioso. Um quadrante trocado não derruba nada — mostra um
rótulo errado com toda a confiança.

Client Component porque ordenar e filtrar precisam de estado. Os dados chegam
como props do Server Component da página; **dado puro atravessa a fronteira
RSC, função não** — a restrição já documentada em `lib/csv.ts`.

Nada muda no backend. `AbcLinha` já traz `unidades`, `visitas` e `conversao`.

## 8. Testes

Em `lib/diagnostico.ts`, porque é lá que o erro é invisível:

- Medianas de conversão e de visitas, com número par e ímpar de produtos.
- Cada um dos quatro quadrantes, nas fronteiras.
- **A trava de número pequeno**: 8 visitas com mediana de 4,8% não recebe
  diagnóstico. Mutação: remover a trava e ver o produto receber um rótulo de
  quadrante com toda a confiança.
- **A cauda é alcançável**: o produto no limiar da amostra tem faixa real para
  ficar abaixo da mediana, não frações de ponto. É o teste que fixa o limiar
  em duas vendas esperadas — sem ele, voltar para uma não quebraria nada.
- **Ausência ≠ zero**: `visitas: null` vira "sem visita colhida", nunca cauda.
- **Menos de 5 diagnosticáveis**: ninguém recebe rótulo.
- Produto exatamente na mediana cai de um lado só, e sempre do mesmo.

## 9. Fora de escopo

- **Gráfico de dispersão** visitas × conversão. Seria a imagem natural do 2×2,
  e foi vetado: a tela Produtos já tem Pareto e cohort, e um terceiro gráfico
  vira poluição.
- **Comparação com o período anterior** (↑↓ na conversão). É o padrão do
  Google Search Console e transforma foto em tendência, mas é a única ideia
  desta rodada que mexe em busca de dado e não só em apresentação.
- **Produtos com visita e zero venda.** Continuam invisíveis: a lista sai de
  `order_items`. Depende de cruzar com o catálogo do ML, e é a próxima da
  spec de visitas.
