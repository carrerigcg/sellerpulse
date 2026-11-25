# Resumo com cartões: o dinheiro e os alertas

Estado: implementado em 2026-11-25 na branch `feat/resumo-com-cartoes`, com a
tela vista (demo, três estados dos alertas, celular) e os revisores sem
bloqueio. O Guilherme testou no localhost e aprovou; vai por PR (toca o
back-end), com merge só depois do CI verde e do ok dele.

## O pedido

Em 2026-11-25 o Guilherme disse que o Resumo parecia "um monte de letra
jogada". Os alertas não alertavam: eram título e parágrafo cinza. E o
dinheiro era uma frase longa. Ele escolheu, nas maquetes:

- o dinheiro em **destaque com cartõezinhos** (opção B);
- os alertas em **duas caixas lado a lado** (opção B);
- a **ordem**: dinheiro, depois alertas, depois "O que fazer agora" (opção A).

"O que fazer agora" fica como está; ele gostou dela.

## Decisões travadas

### 1. A ordem da página

Fica assim: título e período, **O dinheiro**, **Alertas** e **O que fazer
agora**.

O porquê: a página responde primeiro "estou ganhando?", depois "o que está
errado?" e por fim "o que eu faço". Quem abre o painel todo dia não começa
pelo vermelho quando a loja vai bem.

Os alertas continuam só no painel Premium (a demo não tem). Também continuam
aparecendo mesmo sem venda nos 30 dias, como hoje (ver `ResumoDaLoja`): é
quando "anúncio parado" explica o vazio.

### 2. O dinheiro

- **Número grande:**
  - Mostra a sobra arredondada, com a contagem de 0 que já existe
    (`NumeroAnimado`).
  - Com sobra positiva ou zero, embaixo vem "sobraram das suas vendas".
  - Com sobra negativa, em cima vem "faltaram", e embaixo "as vendas não
    cobriram os custos". O número vai sem sinal, porque a palavra diz o
    sentido.
- **Selo de variação ao lado:**
  - **Verde** com "▲ R$ X a mais que os 30 dias anteriores".
  - **Vermelho** com "▼ R$ X a menos que os 30 dias anteriores".
  - **Cinza** em dois casos: "o mesmo que os 30 dias anteriores", ou "sem
    vendas nos 30 dias anteriores para comparar".
  - Seta e texto vão sempre junto da cor.
  - Se algum dos dois meses ficou no negativo, mantém-se o sujeito próprio
    que já existe: "resultado R$ X melhor/pior".
- **Quatro cartõezinhos: Vendas, Comissão do ML, Frete, Custo dos produtos.**
  Saem de `totalizarFluxo`: `receita`, `custo` (taxas do ML), `frete` e
  `custoProdutos`. Nenhum número novo vem do back-end.
  - **Frete:**
    - nada buscado no período (`!temFreteBuscado`): o cartão mostra "—" e
      "ainda buscando";
    - frete buscado só em parte: valor e "parcial".
  - **Custo dos produtos:**
    - cobertura vazia: "—" e "não informado";
    - cobertura parcial: valor e "parcial";
    - cobertura completa: só o valor.
  - Ausência não é zero (`AGENTS.md`). Um "R$ 0" de frete ou de custo afirmaria
    que o vendedor não pagou nada.
- **Embaixo dos cartões:**
  - "Principal motivo: ...";
  - o aviso de comparação;
  - a faixa amarela de custo faltando;
  - o link "Ver o financeiro completo →".
- **A explicação longa** ("É o que fica depois de pagar...") sai, porque os
  cartões já mostram a conta. Fica a lembrança curta: "Aluguel, salários e
  outras despesas ainda saem daí."

### 3. Os alertas

São duas caixas lado a lado (`sm:grid-cols-2`). No celular, uma fica embaixo
da outra. O que vale para as duas:

- **Estado:** cada caixa tem o seu, que decide a cor:
  - **alerta**: vermelho no prejuízo, laranja no parado;
  - **tudo certo**: verde, com ✓;
  - **não medido**: cinza neutro.
- **Não medido nunca é verde.** Sem custo, ou sem produto com ritmo, não se
  sabe se está tudo bem.
- **Texto:** em `ink` ou num tom escuro da mesma cor (vermelho `#b91c1c`,
  laranja `accent-hover`). A cor forte vai na borda, no fundo e no contador.
  O `negative` (#dc2626) em texto sobre fundo tingido fica abaixo de 4,5:1.
- **Máximo:** continua `MAX_POR_TIPO` (5) itens por caixa, com "E mais N".

**Produtos com prejuízo**

- **Itens:** em cada um, o nome do produto e o **prejuízo em destaque**
  (−R$ 312). A receita do período fica menor, embaixo.
- **Botão no pé:** "Conferir custos", que leva para Custos.
- **Sem custo para medir** (`estadoDaMargem === "sem-custo"`): cinza, com
  "Ainda não dá para medir" e o link para Custos.

**Anúncios parados**

- **Itens:** em cada um, o nome do produto (abre o anúncio no ML, como hoje),
  **"18 dias"** em destaque e "costuma vender a cada 2".
- **Pé da caixa:** "Dias contados até DD/MM".
- **Sem sincronização** (`produtos_com_ritmo` nulo) ou sem produto com ritmo
  medido: cinza, com a frase atual de `fraseSemParados`.

### 3b. Decididas no meio da implementação (1.1 e 2.1)

- **Frete ainda sendo buscado (1.1):** além do "parcial" no cartão, uma faixa
  amarela embaixo diz quanto do valor vendido ainda está sem frete e que a
  sobra verdadeira é menor. Sem ela, a sobra parecia maior do que é.
- **Verde só com a maior parte medida (2.1):** a caixa de prejuízo só fica
  verde quando mais da metade dos produtos vendidos nos 30 dias tem custo e
  frete conhecidos. Com menos, fica cinza e diz quantos foram medidos de
  quantos venderam. Para isso o back-end passou a devolver
  `produtos_vendidos` em `/alertas`. Sem o campo (back-end antigo), a regra
  cai para os avaliados e a caixa se comporta como antes.

### 4. As frases

As frases que hoje são uma linha corrida viram partes (valor em destaque e
contexto), como `sobraEmPartes`. A tela monta o destaque, e o teste confere
as partes. As frases inteiras continuam existindo onde alguém as usa.

## Como se prova

- **Teste em `lib/` que cai quando quebra, para cada estado:**
  - o selo nas três direções e sem período anterior;
  - frete "—" sem nada buscado;
  - custo vazio, parcial e completo;
  - o estado de cada caixa de alerta, incluindo "não medido não é verde".
- **Mutação de cada regra nova,** com a cópia restaurada.
- **`scripts/verifica.py`** verde, mais lint, testes e build do front.
- **Tela aberta:**
  - na demo, para o dinheiro;
  - numa rota temporária `zz-previa-*` (nunca commitada), para os estados das
    caixas de alerta, já que a demo não tem alertas;
  - no celular (375px), com o número contado igual ao da tela.

## Fora desta entrega

- Mudar "O que fazer agora".
- Alertas na demo.
- Gráfico no Resumo (a barra "para onde foi o dinheiro" foi a opção C,
  descartada).
- Merge na `main`: só depois do teste do Guilherme e com o ok dele.
