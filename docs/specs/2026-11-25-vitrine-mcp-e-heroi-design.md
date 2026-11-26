# Vitrine: herói animado, MCP e telas novas

Estado: desenhado em 2026-11-25 e aprovado pelo Guilherme. Implementado em
2026-11-26 na branch `feat/vitrine-mcp-e-heroi`: tela vista com movimento,
sem movimento, sem JavaScript e a 375 px; LCP de 740 ms; revisores de código
e de interface sem bloqueio, achados corrigidos. Fora da `main` até ele
testar no localhost.

Pendências opcionais dos revisores: no celular, o canvas fica quase todo
atrás do painel e ainda anima (daria para usar o quadro parado em tela
estreita); a conversa diz "Consultou `visao_geral`", mas `fluxo_financeiro`
seria a ferramenta mais fiel.

## O pedido

Em 2026-11-25 o Guilherme pediu para atualizar a vitrine (`/`). A última
atualização foi a de 2026-10-20 (`2026-10-20-vitrine-atualizacao-design.md`),
e desde então entraram:

- o Premium de volta à venda (`2026-11-17-premium-de-volta-a-venda-design.md`);
- o MCP com a conta real (`2026-11-09-premium-mcp-conta-real-design.md`);
- os alertas no painel;
- as 3 contas, o histórico de 12 meses e a sync a cada 6 horas;
- o Resumo com cartões (`2026-11-25-resumo-com-cartoes-design.md`).

Ele pediu três coisas:

- **destaque para o MCP**;
- **uma animação de escrita** na frase do herói;
- **um fundo de alta qualidade**.

Nas maquetes, escolheu:

| Pergunta | Escolha |
| --- | --- |
| Fundo do herói | **B**: animação própria, em código |
| Estilo da escrita | **1**: máquina de escrever |
| MCP na vitrine | **A**: seção própria e faixa do Premium, sem selo no herói |
| "O que você vê" | **1**: Resumo como primeira aba e fotos novas de todas |

## Medição do vídeo atual

`frontend/public/hero/heroi.mp4`:

- 1280×720, H.264, 30 fps, 20 s e 0,58 Mbps (1,4 MB);
- ampliado, mostra borrão e blocos de compressão;
- o original de 13 MB não está no repositório, e recomprimir não devolve
  nitidez;
- o desenho é de gráfico de bolsa (candles), não de loja.

## Decisões travadas

### 1. Fundo do herói: animação em canvas

- **Saem** `heroi.mp4`, `heroi.jpg` e `HeroVideo`. **Entra** um componente
  client que desenha num `<canvas>`.
- **Conteúdo:**
  - uma grade em perspectiva;
  - barras de vendas que crescem na entrada e depois "respiram";
  - uma linha amarela (a sobra) que se desenha.
  - As cores são as da marca (laranja `accent`/`accent-on-dark`, amarelo
    `highlight`) sobre o escuro.
- **Sem rótulo nem número no gráfico.** Número de enfeite na vitrine seria
  número inventado (`AGENTS.md`).
- **Nitidez:** desenha em `devicePixelRatio`, então fica nítido de 375 px a
  4K.
- **Custo:**
  - para com `IntersectionObserver` quando o herói sai da tela;
  - para com `visibilitychange` quando a aba fica oculta.
- **Movimento reduzido** (`prefers-reduced-motion`) ou economia de dados
  (`saveData`): desenha um quadro parado, o estado final, e não anima.
- **Sem JavaScript:** o fundo da `<section>` é um degradê radial escuro em
  CSS. A página continua correta.
- **Contraste:** o painel `bg-ink/80` atrás do texto fica como está.

### 2. Frase do herói: máquina de escrever

- **H1:**
  - digitada letra a letra, com cursor laranja e pausa depois do ponto;
  - "respostas" sai em `accent-on-dark`;
  - o cursor some uns 2 s depois do fim.
- **Subtítulo:** surge palavra por palavra, desfocado→nítido, depois da H1.
- **Botões:** visíveis desde o início. O "Criar conta" não espera animação.
- **O texto inteiro está no HTML do servidor.**
  - A camada animada é `aria-hidden`.
  - O texto real fica disponível para leitor de tela e busca.
  - O espaço da frase é reservado pelo texto completo invisível, então não há
    salto de layout.
- **Se o JavaScript falhar:** o texto aparece pronto em cerca de 1,2 s, por
  CSS, o mesmo padrão de `NumeroAnimado`. Nunca fica uma frase vazia.
- **Movimento reduzido:** frase pronta, sem animação.
- **Ritmo:** a H1 termina em **cerca de 2 s**, de 30 a 40 ms por letra, mais
  a pausa do ponto. São 54 caracteres: a 40–60 ms, passariam de 2,5 s.
  - O porquê: a H1 é o maior texto da primeira tela, e o LCP só conta quando
    ela termina de aparecer.
  - A maquete levava uns 3 s na H1. Ficou mais ágil de propósito.

### 3. Seção "Pergunte ao Claude" e faixa do Premium

**Seção**

- **Posição:** nova, entre `Acoes` e `HowItWorks`. A história da página fica
  assim: o que você vê → o que você faz → **pergunte à IA** → como começar.
- **Esquerda:**
  - o rótulo "Inteligência artificial" e o selo "Premium";
  - o título "Pergunte ao Claude sobre a sua loja.";
  - dois parágrafos: pergunte em português, e "a IA não chuta: consulta os
    mesmos números do seu painel";
  - três garantias: só leitura, passo a passo de conexão dentro do painel, e
    os mesmos números das telas, dizendo quando falta dado.
- **Direita:** uma conversa de exemplo, que aparece em etapas quando entra na
  tela:
  1. a pergunta: "Quanto sobrou das minhas vendas nos últimos 30 dias?";
  2. a linha "consultou `visao_geral`";
  3. a resposta, com a sobra e as quatro partes;
  4. o rodapé "Exemplo com a loja de demonstração".
- **Os números da resposta vêm da demo, pela mesma conta do Resumo da demo**
  (`veredito`/`partesDaConta`). Nunca são escritos à mão, então nunca
  divergem do `/demo`.
- **De onde vêm:** a busca usa os getters de `lib/demo.ts`
  (`getDemoFluxoFinanceiro`, `getDemoCustos`), com o cache de 1 hora que já
  existe.
- **A conversa fica num `<Suspense>`.** Com o Render frio, a busca pode
  demorar uns 25 s. O Suspense faz essa espera nunca segurar o herói nem o
  resto da página.
- **Se a busca da demo falhar,** a resposta mostra a frase sem tabela e sem
  número. Nunca mostra número velho.
- **Só o Claude é citado.** No ChatGPT, o conector só existe nos planos
  empresariais (mesma regra do cartão do Premium).
- **Nada de dado de vendedor real.** O conector MCP desta máquina está ligado
  à conta real do Guilherme. A vitrine usa só a demo.

**Faixa do Premium**

Fica embaixo da seção, com quatro itens, todos no ar:

| Item | Texto |
| --- | --- |
| Alertas no Resumo | "Produto vendendo com prejuízo e anúncio que parou de vender, logo na primeira tela." |
| Até 3 contas | "Cada conta do Mercado Livre separada, e a soma das três numa tela só." |
| 12 meses de histórico | "Um ano inteiro de vendas no painel, em vez de seis meses." |
| Atualiza a cada 6 horas | "Os números do dia chegam sem você precisar sincronizar." |

### 4. "O que você vê" (`Showcase`)

- **Abas:** Resumo, Financeiro, Produtos e Clientes.
- **Fotos novas** de todas, no computador (1440×900) e no celular, tiradas da
  demo rodando local (`backend-teste` + `frontend`). A foto é tirada depois
  que os números animados terminam de contar.
- Mesmos nomes de arquivo onde a tela já existia, mais `demo-resumo.png` e
  `demo-resumo-mobile.png`.

## Como se prova

- **Teste em `lib/`, que cai quando quebra:**
  - o fatiamento da frase (trechos, destaque e pausas);
  - os números da conversa iguais aos do veredito da demo;
  - sem dado, sem tabela.
- **Mutação** de cada regra, com a cópia restaurada.
- **Verificação:** `scripts/verifica.py` verde, mais `npm test`, lint e build.
- **Tela aberta:**
  - no computador e no celular (375 px), sem rolagem lateral;
  - com movimento reduzido emulado (frase pronta e fundo parado);
  - com o JavaScript bloqueado, se der;
  - com o LCP medido pela `PerformanceObserver`, abaixo de 2,5 s no local.
- **Revisão:** `revisor-de-interface` e `revisor-de-codigo`.

## Fora desta entrega

- O texto do herói (a frase continua a mesma).
- Os preços e os cartões de plano.
- O selo "novo" no herói (opção B do MCP, recusada).
- Vídeo novo de banco de imagens ou gerado.
- Merge na `main`: só depois do teste do Guilherme e do ok dele.
