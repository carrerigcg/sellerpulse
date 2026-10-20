# SellerPulse — Atualização da vitrine

Data: 2026-10-20
Estado: em implementação.

## 1. Por quê

A vitrine foi escrita na Sprint 3, quando o produto tinha três telas. Desde
então entraram custo de produto (PR #11), desempenho dos anúncios com
diagnóstico por quadrante (PR #14) e a aba Exportar com glossário (PR #10) — e
nada disso aparece na página que vende o produto.

Pior que a ausência: **o herói passou a mentir contra si mesmo.** A linha
"O custo do seu produto é o único número que a gente não chuta" foi escrita
quando custo de produto não existia. Hoje existe, com vigência por data e
indicador de cobertura. A vitrine está anunciando uma limitação que o produto
já resolveu.

Os prints de `public/landing/` são anteriores ao card "Custo dos produtos", ao
indicador de cobertura e à seção Desempenho dos anúncios.

## 2. O enquadramento, que é a decisão de verdade

Ele foi explícito: o propósito **não** é o cliente pagar porque há funções
boas, e sim porque entendemos a dor dele e entregamos a solução pronta —
bastando a ele começar.

Isso tem uma consequência estrutural: **lista de funcionalidades está
proibida.** Cinco telas lado a lado no Showcase seria exatamente o catálogo
que o enquadramento rejeita. Cada feature nova entra como uma DOR com a
resposta já montada ao lado, nunca como um recurso com nome e ícone.

## 3. Decisões travadas

**3.1 — Herói: a separação entre ter e entender.** Escolhido entre quatro
alternativas apresentadas.

> Todo vendedor tem os números. Poucos têm as **respostas**.
>
> O Mercado Livre te mostra o que entrou. O SellerPulse mostra o que sobrou,
> qual produto puxa o faturamento, qual anúncio queima visita sem vender e
> qual cliente valia reconquistar — tudo calculado a partir dos seus pedidos
> reais.

O risco desta opção foi levantado e aceito: ela insinua que o visitante está
entre os "poucos que não têm". O subtítulo desarma isso de propósito, pondo a
lacuna no **Mercado Livre** ("te mostra o que entrou"), não em quem lê. Não
reescrever para culpar o vendedor.

A H1 nomeia quatro capacidades, nunca uma — a versão anterior desta spec
liderava só com o funil e foi recusada justamente por reduzir o produto a uma
função.

**3.2 — O herói não carrega a coragem.** Uma H1 que afirma a fórmula E cutuca
o leitor a ser corajoso faz os dois mal, e cobrança na primeira tela afasta.
A fórmula fica no herói; a coragem fecha a página, na faixa final, onde vira
convite:

> Os seus últimos 6 meses já estão lá. Falta você olhar.

**3.3 — Seção nova "Da análise à ação"**, depois do Showcase. Três dores, cada
uma com a resposta pronta. Não são telas:

| Dor | Resposta pronta |
| --- | --- |
| "Esse anúncio é visto e não vende" | Quatro diagnósticos por comparação com a mediana da própria loja, e a ação que cabe em cada um. Sem amostra suficiente, ele **diz isso** em vez de inventar diagnóstico. |
| "Não sei quanto sobra de verdade" | Custo informado uma vez, com a data em que passou a valer, mais o indicador de quanto da receita já tem custo — para saber o quanto confiar na conta. |
| "Preciso dos números fora daqui" | CSV que abre no Excel sem quebrar acento nem coluna, com glossário de cada campo. |

**3.4 — "Como funciona" ganha um 4º passo.** Hoje a sequência termina no
automático ("os 6 meses carregam sozinhos"), e por isso nunca chega no passo
que é do vendedor. O 4º passo é informar o custo — o único número que o
Mercado Livre não sabe, e o que transforma a margem de estimativa em conta
fechada. É aqui que "basta ele começar" vira instrução concreta.

**3.5 — Showcase segue com três análises.** Só os prints e o texto mudam. As
features novas aparecem DENTRO dos prints (card de custo, cobertura,
Desempenho dos anúncios), que é a prova de que não são maquete.

**3.6 — Prints viram script.** A causa de a vitrine ter envelhecido é que os
prints foram capturados à mão e ninguém regera. `npm run prints` usa o Chrome
já instalado em modo headless, nas dimensões que os componentes declaram
(1440×900 e 602×1100). Sem dependência nova.

## 4. Restrições que valem aqui

**Nenhum número inventado na cópia.** Vale a armadilha do `CLAUDE.md`: os
números aparecem nos prints, que são da demonstração real e navegável. A seção
Problem continua com SKUs de exemplo porque está rotulada como ilustração da
forma do problema.

**Nenhuma promessa de crescimento que não se possa sustentar.** "Triplique seu
faturamento" está fora. O impacto vem da tese ("não é sorte, é leitura"), não
de número prometido.

**Verificar no navegador.** `/` é rota dinâmica (`ƒ`); `lint` e `build` passam
com página quebrada. Já aconteceu neste projeto.

## 5. Fora de escopo

Vídeo do herói, domínio próprio, prova social (não há cliente para citar, e
inventar depoimento está fora de questão), e preço — não há plano pago ainda.
