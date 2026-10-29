# SellerPulse — Resumo da loja

Data: 2026-10-23
Estado: mergeada em `5e40f07` (#22), revisada por `revisor-de-interface` e `revisor-de-codigo`. As três decisões da revisão foram tomadas (seção 9).

## 1. Por quê

O público que o SellerPulse quer atender inclui o vendedor mais velho do
Mercado Livre, que não lê gráficos. A avaliação feita na demo em produção, em
2026-10-23, mostrou cinco obstáculos:

1. **As telas são organizadas pela técnica, não pela pergunta do vendedor.**
   "Curva ABC de Pareto", "Cohort de lançamento", "Dispersão RFM", "Conversão
   mediana" — e a tela inicial se chama "Executive". Só Produtos usa sete
   termos técnicos.
2. **O número vem sem veredito.** "Margem de contribuição R$ 164.908, −5,8%
   vs. período anterior" não diz se isso é ruim nem o que fazer. A promessa
   do produto é responder o que a plataforma não responde; as telas param no
   dado e na definição.
3. **Três dos quatro gráficos estão entre os mais difíceis para leigo**:
   dispersão, Pareto com dois eixos e matriz de cohort.
4. **Muito conteúdo, letra pequena.** Produtos tem 6,7 alturas de tela; nela,
   213 blocos de texto estão em 12px, 403 em 14px e nenhum em 16px.
5. **O tutorial explica o conceito, não o número de hoje.**

O que já funciona e serve de modelo: as frases dos segmentos de Clientes
("Já foram bons compradores e estão sumindo — a hora de tentar reengajar é
agora") e os rótulos de ação do diagnóstico de anúncios.

Este projeto ataca 1, 2 e 5 na primeira coisa que o vendedor vê. As telas de
detalhe ficam como estão (seção 9).

## 2. Decisões travadas

Tomadas no brainstorm de 2026-10-23, todas escolhidas pelo dono do produto
entre alternativas apresentadas.

**2.1 — A abertura responde duas perguntas, nesta ordem: "estou ganhando
dinheiro?" e "o que eu faço agora?".** Só o dinheiro informaria sem dizer o
que fazer; só as tarefas mandariam agir sem dizer se a loja vai bem, que é a
primeira angústia de quem vende. Descartado também "como estão as vendas",
que é o que o próprio Mercado Livre já mostra.

**2.2 — Só a tela de Resumo agora.** A melhoria foi dividida em três peças
independentes: (A) o Resumo, (B) a linguagem das telas existentes, (C) a
legibilidade (letra maior, tabelas mais curtas). A vem primeiro porque muda a
primeira impressão sem mexer no que funciona; já nasce em 16px, então leva a
C de graça para si. B vira o próximo projeto, decidido pelo que o Resumo não
resolver.

**2.3 — As frases são montadas por regra, não por IA.** Modelos fixos
preenchidos com os números do vendedor: previsíveis, testáveis, sem custo por
visita, e sem como inventar número — a regra mais cara do projeto. Uma IA
que reescreva as frases pode vir depois, sem tocar nos números.

**2.4 — Período fixo: últimos 30 dias contra os 30 anteriores, sem
seletor.** "O último mês" é a unidade desse vendedor, e a primeira tela não
deve exigir decisão. Cada tarefa leva o período no link, para o número da
tela de destino bater com o do cartão.

**2.5 — O Resumo é a porta de entrada.** Assume `/dashboard` e `/demo`; o
Executive vai para `/dashboard/financeiro` e `/demo/financeiro` e passa a se
chamar "Financeiro". Login, cadastro e a vitrine já apontam para as rotas de
entrada, então nenhum link muda.

## 3. Comportamento

### Período

Últimos 30 dias no fuso do vendedor, terminando em hoje, com o mesmo
"Até" exclusivo das outras telas — `de = hoje − 30`, `ate = hoje`. O
anterior vem de `janelaAnterior`. A tela **não** mostra o "Até" exclusivo:
diz o período com as duas pontas incluídas, "de 23/09 a 22/10" (`ate − 1`).

Exceção, explicada na tarefa de clientes: os segmentos usam os últimos 90
dias.

### Bloco "O dinheiro"

A sobra é a margem de contribuição de `totalizarFluxo` — o mesmo número do
cartão do Financeiro para o mesmo período. Valores em reais inteiros,
arredondados como o `Intl` arredonda (meio para longe do zero), para baterem
com os cartões quando o vendedor clicar — inclusive quando falta dinheiro.

- **A diferença é dita em reais, não em porcentagem.** "R$ 300 a mais" não
  alarma como "+100%" numa base pequena, e dispensa um limiar de "poucos
  pedidos" — que seria número inventado.
- **A comparação tem sujeito.** Com os dois meses no positivo, "a mais do que
  sobrou"; com algum mês no negativo, "O resultado foi R$ X melhor/pior" —
  sem sujeito próprio, "a mais" pegaria carona no "faltaram" de cima e se
  leria ao contrário.
- **A explicação diz o que a sobra descontou — e o que não.** Com cobertura
  zero ela não afirma "depois de pagar os produtos": diz que o custo dos
  produtos ainda não foi descontado. Com sobra negativa, troca "é o que fica"
  por "na conta entram". Sempre lembra que aluguel, salários e outras
  despesas ainda saem dali: é margem de contribuição sem o nome técnico, e
  sem ser vendida como lucro (`project-decisao-margem-vs-lucro`).
- **"Principal motivo"** decompõe a diferença nas três partes da conta —
  vendas, tarifas do Mercado Livre e frete, custo dos produtos — e nomeia a
  que contribuiu mais **no sentido da mudança**. Antes do arredondamento as
  três fecham a diferença (`margem_contribuicao` é receita − comissão − frete
  − custo dos produtos); depois dele podem se afastar em um ou dois reais, e
  numa diferença de R$ 1 nenhuma parte pode ter andado no mesmo sentido —
  então a linha some. Diz sempre a verdade sobre a parte: nunca é trocada
  por outra explicação.
- **Aviso de comparação.** Quando a cobertura de custo muda entre os meses
  (`pct` diferente) **no mesmo sentido** do custo dos produtos, uma linha a
  mais avisa que parte da diferença vem do custo informado. Mais vendas com
  custo fazem o custo subir sem a loja ter piorado; se a cobertura caiu e o
  custo subiu mesmo assim, a alta é real — e o aviso não aparece, para não
  calá-la. Independe de qual parte é o principal motivo: a cobertura
  distorce a comparação inteira.
- **Aviso de cobertura** quando a do período atual é menor que 100%, no
  passado ("saiu sem custo"): o custo vale da data em que foi informado em
  diante, então quem acabou de preencher tudo ainda vê o aviso por até 30
  dias — no presente, ele desmentiria o que a pessoa acabou de fazer.

### Bloco "O que fazer agora"

Ordem fixa, só os cartões que se aplicam:

1. **Produtos sem custo.** Conta os produtos vendidos no período cujo custo
   está vazio **hoje** (`getCustos`, `custo_unitario === null`) — a mesma
   conta da tela de Custos. Contar pela venda passada (`produtosSemCusto` da
   curva ABC) daria outro número, porque custo informado hoje não volta para
   trás; o apoio diz isso ("as próximas vendas"), para o efeito não parecer
   sumido.
2. **Anúncios vistos e rejeitados.** `calculaReferencia` + `diagnostica`, a
   mesma regra da seção Desempenho dos anúncios. Só aparece se a referência
   for confiável. O link abre Produtos já filtrado nesse diagnóstico. A frase
   diz "mais visitas que a média da sua loja, mas vendem menos" — relativo,
   como a regra é — e não "vendem pouco".
3. **Clientes que sumiram.** Segmento "At Risk" dos **últimos 90 dias**. O
   segmento é calculado dentro da janela: a recência conta do fim do período
   e as notas são quintis entre os compradores daquela janela
   (`segmentation_pg.py`, `rfm_scores`); em 30 dias, "Em risco" passaria a
   significar "comprou há 25 dias". A regra é recência baixa **e**
   (frequência **ou** valor altos), então a frase diz "já compraram bem" —
   não "compravam bem", que afirmaria frequência — e o fato que vale para
   todos: há quantos dias, no mínimo, não compram. O link abre Clientes já
   filtrado nesse segmento e rolado até a tabela.

**Sem cartão de "converte, falta ser visto"** — decidido pelo dono na
revisão (seção 9). O diagnóstico continua na seção de Produtos.

**Rodapé.**
- Uma fonte falhou: os cartões das fontes que carregaram aparecem, e a tela
  diz que parte do resumo não carregou — **nunca** "nada pedindo atenção",
  que seria afirmar algo sem o dado.
- Nenhuma tarefa e anúncios avaliados: "Nada pedindo atenção agora."
- Nenhuma tarefa, mas sem régua confiável para os anúncios: diz que custos e
  clientes estão bem e que os anúncios ainda não têm visitas para avaliar.
  Faltar o dado não é o mesmo que não ter problema.

Os botões das tarefas são secundários (contorno), não laranja: nenhuma
tarefa é mais importante que as outras, e a direção visual é um só botão de
ação primária por tela.

Quem chega a Produtos ou a Clientes por um cartão não vê o tutorial abrir
sozinho por cima da lista que veio ver (`chegouFiltrado` em
`deveAbrirSozinho`), e nada é marcado como visto: o tutorial abre na próxima
visita direta.

### Estados

| estado | o que a tela mostra |
| --- | --- |
| fluxo (atual ou anterior) falhou, no dashboard | "Não foi possível carregar o resumo agora…"; sessão expirada ganha o link "Entrar de novo". Não usa `mensagemDeFalhaAoCarregar`, cujo "O backend está no ar?" só assusta quem não sabe o que é backend |
| fluxo falhou, na demo | a mensagem de erro da demo |
| nenhuma venda nos 30 dias, no dashboard | vazio próprio: pode ser importação em andamento, ou só um mês sem venda — com atalhos para os últimos 3 meses e para conectar. Não o `SemPedidosNoPeriodo`, que manda conectar quem já conectou |
| nenhuma venda nos 30 dias, na demo | a mensagem de vazio da demo, sem atalho de conectar |
| sem vendas nos 30 dias anteriores | a sobra sem comparação, dizendo que não há com o que comparar |
| sobra negativa | a frase de falta, a comparação com sujeito próprio e a explicação de falta |

O texto de erro é `ink` sobre o fundo vermelho claro, com a cor na borda:
`negative` sobre `negative/10` fica perto de 4,1:1 em 16px.

### Letra e toque

Texto base de 16px, frase principal de 24px, botões com 44px de altura.

## 4. Textos

`{R$ x}` é o valor em reais inteiros; plural e singular são parte do modelo.

**Cabeçalho:** "Sua loja nos últimos 30 dias" · "de {dd/mm} a {dd/mm}".

**Dinheiro:**

| caso | frase |
| --- | --- |
| sobra ≥ 0 | Sobraram {R$ sobra} das suas vendas. |
| sobra < 0 | As vendas não cobriram os custos: faltaram {R$ \|sobra\|}. |
| os dois meses ≥ 0, diferença ≠ 0 | {R$ \|dif\|} a {mais\|menos} do que sobrou nos 30 dias anteriores. |
| algum mês < 0, diferença ≠ 0 | O resultado foi {R$ \|dif\|} {melhor\|pior} que nos 30 dias anteriores. |
| diferença = 0 | O mesmo que nos 30 dias anteriores. |
| sem anterior | Não houve vendas nos 30 dias anteriores para comparar. |

**Explicação:**

A frase é montada por partes (`explicacao` em `lib/resumo.ts`): a lista do
que já foi pago e, depois de um travessão, o que ainda falta.

| parte | entra na lista do que foi pago quando | senão, a ressalva |
| --- | --- | --- |
| comissão do Mercado Livre | sempre | — |
| frete | todo o frete do período foi buscado | "o frete ainda está sendo buscado no Mercado Livre" (nada buscado) ou "o frete de parte das vendas ainda está sendo buscado no Mercado Livre" (parte) |
| produtos | há algum custo informado | "o custo dos produtos ainda não foi descontado" |

| caso | frase |
| --- | --- |
| sobra ≥ 0, tudo completo | É o que fica depois de pagar a comissão do Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas também saem daí. |
| sobra ≥ 0, frete pela metade | É o que fica depois de pagar a comissão do Mercado Livre e os produtos — o frete de parte das vendas ainda está sendo buscado no Mercado Livre. Aluguel, salários e outras despesas também saem daí. |
| sobra < 0, nada de frete nem de custo | Na conta entra a comissão do Mercado Livre — o frete ainda está sendo buscado no Mercado Livre, e o custo dos produtos ainda não foi descontado. Aluguel, salários e outras despesas vêm depois. |

**Principal motivo:**

| parte | frase |
| --- | --- |
| vendas | Principal motivo: as vendas {subiram\|caíram} {R$ x} — de {R$ a} para {R$ b}. |
| comissão do Mercado Livre | Principal motivo: a comissão do Mercado Livre {subiu\|caiu} {R$ x}. |
| frete | Principal motivo: o frete que você pagou {subiu\|caiu} {R$ x}. |
| custo dos produtos | Principal motivo: o custo dos produtos {subiu\|caiu} {R$ x}. |
| aviso de comparação | Parte da diferença vem do custo informado: neste período, {p}% do valor vendido tinha custo; no anterior, {q}%. |

**Aviso de cobertura:**

| caso | frase |
| --- | --- |
| parcial | {100 − pct}% do valor vendido neste período saiu sem custo informado — a sobra verdadeira é menor que essa. |
| nenhum custo | Nenhuma venda deste período saiu com custo informado. |

"Período", não "mês": a janela vai de 23/09 a 22/10, e "deste mês" se leria
como outubro. "Do valor vendido", não "das vendas": o percentual é sobre o
valor, não sobre o número de pedidos.

Link ao fim do bloco: "Ver o financeiro completo" → `{base}/financeiro?de&ate`.

**Tarefas:**

| tarefa | frase | apoio | botão → destino |
| --- | --- | --- | --- |
| custos | {n} produto(s) que você vendeu {está\|estão} sem custo informado | Com o custo informado, a margem desconta o produto — e você escolhe se vale também para as vendas passadas. | "Informar custos" (demo: "Ver custos") → `{base}/custos?de&ate` |
| vistos e rejeitados | {n} {anúncio recebe\|anúncios recebem} mais visitas que a média da sua loja, mas {vende\|vendem} menos | Muita gente entra e não compra — vale revisar preço, foto, título ou frete. | "Ver os que vendem menos" → `{base}/produtos?de&ate&diagnostico=visto-e-rejeitado#desempenho-anuncios` |
| clientes | {n} {cliente que já comprou\|clientes que já compraram} bem com você não {compra\|compram} há {d} dias ou mais | Nos últimos 3 meses, {gastou\|gastaram} {R$ x} com você. | "Ver quais clientes" → `{base}/clientes?de&ate&segmento=em-risco#compradores` (janela de 90 dias) |
| nenhuma, anúncios avaliados | Nada pedindo atenção agora. | — | — |
| nenhuma, anúncios sem régua | Nada pedindo atenção nos custos e nos clientes. Os anúncios ainda não têm visitas suficientes para avaliar. | — | — |
| incompleto | Parte do resumo não carregou agora. Tente de novo em instantes. | — | — |

`{d}` é o menor `recency_dias` do grupo. "Média da sua loja" e não "mediana":
é a palavra que a própria seção usa, e a que esse vendedor conhece.

O apoio dos anúncios é escrito para o Resumo, e não reaproveitado de
`APARENCIA`: lá o texto é a legenda técnica da seção ("converte abaixo da
média"), aqui é para quem nunca a leu. Os fatos são os mesmos.

## 5. Arquitetura

**`frontend/lib/resumo.ts` — regras e textos, sem React.** Funções puras,
testáveis no vitest, no padrão de `lib/tutoriais.ts`:

```ts
montaVeredito(entrada: {
  atual: Totais;                   // ReturnType<typeof totalizarFluxo>
  anterior: Totais | null;         // null = sem vendas no período anterior
  coberturaAtual: Cobertura;       // coberturaDoFluxo
  coberturaAnterior: Cobertura | null;
}): Veredito;

montaTarefas(entrada: {
  custos: { custo_unitario }[] | null;   // null = a busca falhou
  abc: LinhaDeFunil[] | null;
  rfm: { segmento, monetary, recency_dias }[] | null;
  links: LinksDoResumo;                  // já com base e período
}): { tarefas: Tarefa[]; incompleto: boolean; anunciosAvaliados: boolean };

montaResumo(entrada: {
  fluxo, anterior, abc, custos, rfm: PromiseSettledResult<…>;
  links: LinksDoResumo;
}): { erroNoFluxo, semVendas, veredito, tarefas, rodape, hrefFinanceiro };
```

`Veredito` e `Tarefa` carregam as frases prontas — o texto mora aqui para o
vitest cobrir a regra e o plural, não só a conta. `montaResumo` é tudo o que
as páginas faziam com o resultado das buscas: as regras "fluxo com erro
derruba" e "anterior vazio não compara" ficavam fora do alcance do vitest, e
as duas páginas repetiam a montagem. `Totais` sai do próprio
`totalizarFluxo`, importado por caminho relativo — é a conta dos cartões do
Financeiro, e repeti-la seria o jeito de a sobra e a margem divergirem.

**`periodoDoResumo()` em `frontend/lib/periodo.ts`**, ao lado de
`periodoPadrao`: `{ de, ate, legenda }` com a legenda já inclusiva.

**`frontend/components/resumo/`** — `bloco-dinheiro.tsx`,
`lista-de-tarefas.tsx` e `resumo-da-loja.tsx` (cabeçalho, estados e os dois
blocos), Server Components sem interação.

**Páginas.** `app/dashboard/page.tsx` e `app/demo/page.tsx` viram o Resumo.
Cada uma busca com os próprios getters, em paralelo e com
`Promise.allSettled`, entrega tudo a `montaResumo` e escreve só o que depende
do contexto — a mensagem de erro e o estado vazio. A da demo chama
`connection()` antes de tudo (seção 6):

| busca | janela |
| --- | --- |
| fluxo atual e anterior | 30 + 30 dias |
| curva ABC | 30 dias |
| custos | 30 dias |
| RFM | 90 dias (`periodoPadrao`) |

Todas existem hoje, nos dois contextos — sem mudança de backend. As duas
buscas de fluxo são obrigatórias: qualquer uma com erro derruba a tela, porque
sem a anterior a frase de comparação mentiria por omissão. As outras viram
`null` e marcam o resumo incompleto. Fluxo anterior que volta **vazio** (sem
erro) é `anterior: null` — "não houve vendas para comparar".

**O que muda no que existe:**

- O conteúdo atual de `app/dashboard/page.tsx` e `app/demo/page.tsx` move
  para `app/dashboard/financeiro/page.tsx` e `app/demo/financeiro/page.tsx`,
  sem mudança de conteúdo além do título ("Financeiro").
- `DisparaDelta` (`app/dashboard/delta.tsx`) fica no Resumo: é a porta de
  entrada que dispara a sincronização ao entrar. Mudar junto com o Executive
  faria a sincronização do login parar sem ninguém perceber.
- `components/nav/itens.ts`: "Resumo" primeiro, com ícone novo em
  `icones.tsx`; "Executive" vira "Financeiro" em `/financeiro`.
- `DesempenhoAnuncios` ganha a prop `filtroInicial?: Diagnostico`. As
  páginas de Produtos leem `?diagnostico=`, validam com `diagnosticoDaUrl`
  (`lib/diagnostico.ts`) e passam também `key={filtroInicial ?? "todos"}`: o
  Next reaproveita o componente quando só a query muda, e o filtro ficaria
  preso ao voltar a `/produtos` pela barra lateral. Os chips ganham
  `aria-pressed` — quem chega pelo cartão precisa saber que a lista está
  filtrada.
- `BuyersTable` ganha chips de segmento e a prop `filtroInicial?:
  SegmentoRfm`, no mesmo desenho. As páginas de Clientes leem `?segmento=`,
  validam com `segmentoDaUrl` (`lib/segmento-da-url.ts`) e passam `key` pelo
  filtro, pelo mesmo motivo. O valor da URL é o `parametro` de cada segmento
  em `segmentos.ts` (`em-risco`, não `At Risk`): em português e sem espaço,
  como o `?diagnostico=`. O link do Resumo sai de `parametroDoSegmento`, e um
  teste confere que a página reconhece o que o link manda. O segmento ativo
  aparece mesmo com zero clientes, para a lista vazia ter explicação. O chip
  é um componente só (`chip-de-filtro.tsx`) nas duas telas.
- `scripts/captura-prints.mjs`: o print do Executive passa a vir de
  `/demo/financeiro`. Os prints não são regerados agora.
- Vitrine (`showcase.tsx`) e cadastro (`signup/page.tsx`): o cartão
  "Executive" vira "Financeiro", e o "Ver tela completa" da vitrine passa a
  levar a `/demo/financeiro` — em `/demo` ele abriria o Resumo ao lado do
  print do Financeiro.
- O tutorial do Financeiro continua com `tela="executive"` e a mesma chave
  de "já vi". O Resumo não usa `CabecalhoDeTela`, então não tem tutorial nem
  seletor — não precisa explicar a si mesmo.

## 6. Verificação

**Testes (vitest), em `lib/resumo.test.ts`:**

- sobra positiva, negativa e zero; diferença a mais, a menos, igual; sem
  anterior; meses negativos (melhor e pior); arredondamento de falta no meio
  do real;
- principal motivo: a parte certa nos três casos, inclusive com partes em
  sentidos opostos, e nenhum quando a diferença é de arredondamento;
- aviso de comparação: dispara com cobertura e custo no mesmo sentido, cala
  quando a alta de custo é real, e aparece mesmo quando o motivo é outra
  parte;
- explicação com cobertura zero; aviso de cobertura parcial, nenhum,
  completo;
- tarefas: ordem fixa, cartão com zero some, anúncios somem sem referência
  confiável (e ficam "não avaliados"), plural e singular, e o cartão
  "pouco vistos" não aparece mesmo com anúncio nesse diagnóstico;
- rodapé: `incompleto` nunca vira "nada pedindo atenção", nem anúncio sem
  régua;
- `montaResumo`: fluxo atual ou anterior com erro derruba, anterior vazio
  não compara, sem venda vira estado vazio;
- links levam base, período e filtro; `periodoDoResumo`: 30 dias, legenda
  inclusiva;
- `segmentoDaUrl` (em `lib/segmento-da-url.test.ts`): só aceita o parâmetro
  em português, os parâmetros não precisam de escape, e o `?segmento=` do
  cartão de clientes é o que a página reconhece. Duas mutações derrubam os
  testes certos: validar pela chave em inglês e pôr espaço no parâmetro.

**Mutação** — quebrar de propósito, confirmar com `diff` que a troca entrou,
ver o teste certo cair, restaurar. Sete regras, todas derrubaram o teste
delas:

1. o aviso de comparação ignorando a direção;
2. a explicação ignorando cobertura zero;
3. a comparação sem sujeito próprio com mês negativo;
4. o arredondamento com `Math.round`;
5. o rodapé ignorando anúncios não avaliados;
6. `incompleto` virando "nada pedindo atenção";
7. a contagem de custo contando todos os produtos.

**Build:** medido que, sem `connection()`, `/demo` sai `○` com revalidação
de 1h — com ele, `ƒ`.

**Navegador, em `/demo` com o banco de teste semeado:** cada tarefa clicada
abre a tela com o **mesmo número** do cartão (Custos, Produtos já filtrado e
rolado, Clientes); Financeiro em `/demo/financeiro` com o tutorial; a
vitrine leva ao Resumo; 390px; console limpo numa aba nova.

**Entrega por PR** com preview da Vercel, apesar de ser só front. A troca
mexe na porta de entrada de quem está logado, e o dashboard exige login: o
dono confere no preview antes do merge. Depois, o `verificador-de-entrega`
confirma produção nas duas plataformas.

## 7. Acessibilidade

- Contraste: tokens atuais, já medidos (`globals.css`).
- Diferença para menos em texto **e** cor, nunca só cor.
- Botões com nome do destino, não "Ver mais" ("Ver os que vendem menos",
  "Ver quais clientes"): uma lista de links com o mesmo nome para destinos
  diferentes não diz nada a quem usa leitor de tela.
- Chip de filtro com `aria-pressed`.
- Uma só `h1`; os blocos são `section` com título.

## 8. Fora de escopo

A linguagem das outras telas (projeto B), letra maior nelas (projeto C), IA
para reescrever as frases e regerar os prints da vitrine.

## 9. Achados no caminho

**Segmentos dependem da janela.** O RFM é relativo ao período consultado
(seção 3). Uma tela que mostre segmentos num recorte curto mostra
segmentos enganosos — vale para qualquer uso futuro, não só o Resumo.

**Importação em andamento pode virar um "caiu" falso.** A importação
inicial vai do mais antigo para o mais novo, então durante ela o período
anterior pode estar completo e o atual, parcial. O status `historico_completo`
existe, mas o Resumo não o consulta. O problema é anterior (o Financeiro tem
o mesmo), só que agora vira frase.

**Decisões da revisão**, tomadas pelo dono em 2026-10-23 (seguiu as
recomendações):

1. **Os dois cartões de anúncio saíam quase sempre juntos e com o mesmo
   número.** Com o corte na mediana nos dois eixos, rejeitados − pouco
   vistos ≈ (acima da mediana de visitas) − (acima da mediana de conversão)
   ≈ 0. Medido: demo 11 e 11; loja real 36 e 33. **Decidido: tirar o cartão
   "pouco vistos"**, cuja ação era a mais vaga. O de rejeitados ainda
   aparece para quase toda loja com régua confiável — a comparação é com a
   própria loja, por desenho — e por isso a frase diz "mais que a média da
   sua loja", não "vendem pouco".
2. **O tutorial de Produtos abria por cima da seção filtrada.** **Decidido:
   não abrir sozinho quando a pessoa chega filtrada**, sem marcar como visto
   (`chegouFiltrado`, spec do tutorial, seção 3).
3. **"Ver quais clientes" levava à lista inteira**, ordenada por valor e com
   os em risco espalhados no meio. Ficou fora do PR e **foi feito logo
   depois do merge**, direto na `main`: o link leva
   `?segmento=em-risco#compradores`, a tabela abre filtrada nesse segmento e
   o tutorial de Clientes não abre por cima dela (seção 5).

**O frete não é calculado** (auditoria de números, 2026-10-27). Na conta real,
1.091 de 1.091 pedidos pagos chegavam com frete R$ 0,00: a ingestão lê um campo
que o Mercado Livre nunca preenche, e o custo do vendedor só existe na consulta
de cada envio. As frases afirmavam um desconto que não acontecia, e a demo
(sintética, com frete) mostrava uma conta que o produto real não faz. Até o
frete existir, `lib/frete.ts` trata o frete como ausência nos dois contextos:
a margem sai sem ele e toda frase diz que ele ainda não entra. Erro estimado
pela auditoria: de 0% a ~5,4% da receita a mais na sobra.

**O frete passou a ser buscado** no mesmo dia, por envio
(`docs/specs/2026-10-27-frete-real-design.md`). A explicação ganhou um
terceiro estado, "buscado só em parte", porque logo depois de conectar a conta
a colheita está pela metade.
