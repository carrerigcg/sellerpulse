# SellerPulse — Resumo da loja

Data: 2026-10-23
Estado: aguardando revisão do dono do produto.

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
   todos: há quantos dias, no mínimo, não compram.
4. **Anúncios que convertem e não são vistos.** Mesma regra do item 2,
   diagnóstico `converte-falta-ser-visto`.

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
ação primária por tela. Os dois de anúncio têm nomes diferentes — levam a
filtros diferentes.

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

| caso | frase |
| --- | --- |
| sobra ≥ 0, com algum custo | É o que fica depois de pagar o Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas ainda saem daí. |
| sobra ≥ 0, cobertura zero | É o que fica depois de pagar o Mercado Livre e o frete — o custo dos produtos ainda não foi descontado. Aluguel, salários e outras despesas também saem daí. |
| sobra < 0, com algum custo | Na conta entram o Mercado Livre, o frete e os produtos. Aluguel, salários e outras despesas vêm depois. |
| sobra < 0, cobertura zero | Na conta entram o Mercado Livre e o frete — o custo dos produtos ainda não foi descontado. Aluguel, salários e outras despesas vêm depois. |

**Principal motivo:**

| parte | frase |
| --- | --- |
| vendas | Principal motivo: as vendas {subiram\|caíram} {R$ x} — de {R$ a} para {R$ b}. |
| Mercado Livre e frete | Principal motivo: as tarifas do Mercado Livre e o frete {subiram\|caíram} {R$ x}. |
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
| custos | {n} produto(s) que você vendeu {está\|estão} sem custo informado | Com o custo informado, as próximas vendas já descontam o produto. | "Informar custos" (demo: "Ver custos") → `{base}/custos?de&ate` |
| vistos e rejeitados | {n} {anúncio recebe\|anúncios recebem} mais visitas que a média da sua loja, mas {vende\|vendem} menos | Muita gente entra e não compra — vale revisar preço, foto, título ou frete. | "Ver os que vendem menos" → `{base}/produtos?de&ate&diagnostico=visto-e-rejeitado#desempenho-anuncios` |
| clientes | {n} {cliente que já comprou\|clientes que já compraram} bem com você não {compra\|compram} há {d} dias ou mais | Nos últimos 3 meses, {gastou\|gastaram} {R$ x} com você. | "Ver quais clientes" → `{base}/clientes?de&ate` (janela de 90 dias) |
| convertem, pouco vistos | {n} {anúncio vende\|anúncios vendem} mais que a média da sua loja quando {é visto\|são vistos}, mas {recebe\|recebem} poucas visitas | Vale dar mais visibilidade a {ele\|eles}. | "Ver os pouco vistos" → `…&diagnostico=converte-falta-ser-visto#desempenho-anuncios` |
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
  atual: TotaisDoFluxo;            // de totalizarFluxo
  anterior: TotaisDoFluxo | null;  // null = sem vendas no período anterior
  coberturaAtual: Cobertura;       // coberturaDoFluxo
  coberturaAnterior: Cobertura | null;
}): Veredito;

montaTarefas(entrada: {
  custos: CustoLinha[] | null;     // null = a busca falhou
  abc: AbcLinha[] | null;
  rfm: RfmLinha[] | null;
  links: LinksDoResumo;            // já com base e período
}): { tarefas: Tarefa[]; incompleto: boolean };
```

`Veredito` e `Tarefa` carregam as frases prontas — o texto mora aqui para o
vitest cobrir a regra e o plural, não só a conta.

**`periodoDoResumo()` em `frontend/lib/periodo.ts`**, ao lado de
`periodoPadrao`: `{ de, ate, legenda }` com a legenda já inclusiva.

**`frontend/components/resumo/`** — `bloco-dinheiro.tsx` e
`lista-de-tarefas.tsx`, Server Components sem interação.

**Páginas.** `app/dashboard/page.tsx` e `app/demo/page.tsx` viram o Resumo.
Cada uma busca com os próprios getters, em paralelo e com
`Promise.allSettled`:

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
  páginas de Produtos leem `?diagnostico=` e validam contra
  `ORDEM_DOS_FILTROS` antes de repassar — texto puro, atravessa a fronteira
  RSC.
- `scripts/captura-prints.mjs`: o print do Executive passa a vir de
  `/demo/financeiro`. Os prints não são regerados agora.
- O tutorial do Financeiro continua com `tela="executive"` e a mesma chave
  de "já vi". O Resumo não usa `CabecalhoDeTela`, então não tem tutorial nem
  seletor — não precisa explicar a si mesmo.

## 6. Verificação

**Testes (vitest), em `lib/resumo.test.ts`:**

- sobra positiva, negativa e zero; diferença a mais, a menos, igual; sem
  anterior;
- "o que mais pesou" escolhe a parte certa nos três casos, inclusive quando
  duas partes se movem em sentidos opostos;
- proteção da cobertura: custo como maior peso com coberturas diferentes
  não culpa o custo;
- aviso de cobertura parcial, nenhum, completo (sem aviso);
- tarefas: ordem fixa, cartão com zero some, anúncios somem sem referência
  confiável, plural e singular;
- `incompleto` nunca produz "Nada pedindo atenção agora";
- links levam base, período e filtro;
- `periodoDoResumo`: 30 dias, legenda inclusiva.

**Mutação**, nas três regras que carregam peso — quebrar de propósito,
confirmar que o teste cai, restaurar, com o `diff` antes de rodar:

1. a proteção da cobertura;
2. `incompleto` contra "nada pedindo atenção";
3. a contagem de custo pelo que falta **hoje**.

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
- Botões com nome do destino ("Ver quais anúncios"), não "Ver mais".
- Uma só `h1`; os blocos são `section` com título.

## 8. Fora de escopo

A linguagem das outras telas (projeto B), letra maior nelas (projeto C), IA
para reescrever as frases, filtro por segmento na tela de Clientes, e
regerar os prints da vitrine.

## 9. Achados no caminho

**Segmentos dependem da janela.** O RFM é relativo ao período consultado
(seção 3). Uma tela que mostre segmentos num recorte curto mostra
segmentos enganosos — vale para qualquer uso futuro, não só o Resumo.
