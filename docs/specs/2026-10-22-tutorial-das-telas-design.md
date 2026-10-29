# SellerPulse — Tutorial das telas

Data: 2026-10-22
Estado: mergeada em `a8d0764` (#21), revisada por `revisor-de-interface` e `revisor-de-codigo`. Premissa da 2.3 confirmada.

## 1. Por quê

As telas de análise usam conceitos que não se explicam sozinhos: margem de
contribuição não é lucro, classe A é "os primeiros 80% da receita", um
anúncio "visto e rejeitado" é comparado com a mediana da própria loja, o
"Até" do seletor é exclusivo. Quem chega pela primeira vez vê os números e
não sabe o que eles afirmam.

A ideia veio do dono do produto: um pop-up centralizado, fundo desfocado,
em carrossel, com opção de avançar e de fechar.

## 2. Decisões travadas

Tomadas no brainstorm de 2026-10-22. As quatro primeiras foram escolhidas
pelo dono do produto entre alternativas apresentadas.

**2.1 — Formato: modal centralizado em carrossel.** Alternativas descartadas:
tour com destaque ancorado nos elementos (quebra quando o layout muda, e a
navegação lateral tem três modos responsivos) e dicas permanentes ao lado de
cada conceito (não interrompe, mas não dá a experiência de tutorial pedida).

**2.2 — Abre sozinho na primeira visita a cada tela.** Um tutorial curto por
tela, não um tutorial único no primeiro acesso: cada um explica o que está
na frente da pessoa naquele momento.

**2.3 — Só na demo e no dashboard logado. Nunca na vitrine (`/`).** Palavras
do dono do produto: a vitrine já mostra o que a aplicação entrega, e o pop-up
lá é desnecessário.

> **Premissa confirmada pelo dono em 2026-10-23:** a frase foi "esse pop-up vem
> só na tela da demo e quando logado", e a li como **abrir sozinho também na
> demo**, o que substitui a recomendação original (na demo, só pelo botão "?",
> para não pôr um modal na primeira impressão de quem está avaliando). Com o
> tutorial em produção — 13 slides somando as cinco telas da demo — a resposta
> foi manter: "assim está perfeito". Não reabrir sem dado novo.

**2.4 — "Já vi" fica no `localStorage` do navegador.** Sem migration, sem
RLS, sem PR de backend. O custo aceito: não acompanha a pessoa entre
aparelhos.

**2.5 — O botão "Como usar esta tela" reabre o tutorial.** Decisão de
desenho, não do dono: sem ele, quem fecha por reflexo perde o conteúdo para
sempre — o defeito mais comum de tutorial em pop-up.

**2.6 — Não abre sozinho sobre tela vazia ou com erro.** Também decisão de
desenho. Um usuário recém-cadastrado cai no dashboard sem pedido e com o
atalho "Conectar uma conta do Mercado Livre" — a ação mais importante da
vida dele no produto. Um modal explicando margem por cima de uma tela sem
número esconde essa ação e explica algo que ele ainda não pode ver. O botão
"?" continua disponível.

**2.7 — O conteúdo explica conceitos, não botões.** O modal cobre a tela, então
"clique aqui para exportar" descreveria algo que a pessoa não está vendo. Cada
slide explica um conceito que a tela não deixa óbvio.

## 3. Comportamento

**Onde aparece.** Nas cinco telas de análise — Executive, Produtos, Clientes,
Custos e Exportar — em `/dashboard` e em `/demo`. O tutorial é montado pelo
`CabecalhoDeTela`, que só essas dez páginas usam; a vitrine e
`/dashboard/conectar` ficam de fora por construção, não por condição.

Desde 2026-10-27, também no **Resumo** (`/dashboard` e `/demo`), montado
pelo `ResumoDaLoja`. A spec do Resumo tinha decidido que ele dispensava
tutorial, por se explicar em frases; o dono sentiu falta do pop-up na tela
de entrada, e ela é justamente onde quem não lê gráfico precisa saber onde
fica cada coisa. O Financeiro (antigo Executive) mantém a chave `executive`.

**Quando abre sozinho.** As quatro condições juntas:

1. a pessoa nunca fechou este tutorial, nesta versão, neste contexto;
2. a tela tem dado para mostrar (nem vazia, nem com erro);
3. o `localStorage` está disponível;
4. a pessoa não chegou por um atalho que já filtra a tela (`chegouFiltrado`).
   Acrescentada com o Resumo da loja (2026-10-23): os cartões de anúncios e
   de clientes abrem Produtos e Clientes rolados e filtrados, e um modal por
   cima esconderia exatamente o que a pessoa veio ver. Como não abre, não marca como visto — abre na próxima
   visita direta.

Se o `localStorage` falhar (aba anônima, armazenamento bloqueado), **não abre
sozinho**: sem como lembrar, abriria em toda visita. O botão "?" funciona.

**Chave do "já vi":** `sellerpulse:tutorial:{contexto}:{tela}:v{versao}`, com
`contexto` em `demo` ou `dashboard`. Contextos separados de propósito: quem
viu na demo e criou conta vê de novo, agora com os próprios números — e o
conteúdo de Custos é diferente nos dois. Mudou o texto de uma tela, sobe a
`versao` e o tutorial reaparece só para aquela tela.

**Quando marca como visto.** Ao fechar, por qualquer caminho: ✕, ESC, clique
fora do modal ou "Entendi" no último slide. Não ao abrir — quem recarregar
a página no meio vê de novo, o que é o comportamento certo.

**Navegação.**

| elemento | comportamento |
| --- | --- |
| **Próximo** | botão primário (laranja); no último slide vira **Entendi** e fecha |
| **Voltar** | secundário; não aparece no primeiro slide |
| **✕** | canto superior direito, fecha |
| ← → | navegam entre slides |
| ESC / clique fora | fecham |
| progresso | pontos + "2 de 3"; tutorial de um slide não mostra progresso |

Um só botão laranja no modal, seguindo a direção visual: laranja é ação, e
duas ações laranja significam nenhuma ação principal. O botão "?" no
cabeçalho é discreto (cinza), nunca laranja — ele não é a ação da tela.

**Aparência.** Modal centralizado, até `max-w-md`, com 1rem de margem no
celular. Fundo escurecido e desfocado (`::backdrop`). Troca de slide com
transição curta, desligada quando o sistema pede movimento reduzido.

## 4. Conteúdo

Máximo de três slides por tela. Cada afirmação tem fonte no código, porque
texto que descreve o produto errado é a mesma falha de número inventado.

**Os textos são neutros quanto ao contexto** — servem na demo e no dashboard
sem trocar "você" por "o vendedor". Só Custos tem uma versão própria para a
demo, porque lá a tela é outra coisa: só leitura. Uma lista inteira de
variantes para mudar uma palavra num slide duplicaria os outros dois, e
conteúdo duplicado diverge — a mesma razão das refatorações de duplicação
que antecederam esta feature.

### Resumo

| # | título | texto | fonte |
| --- | --- | --- | --- |
| 1 | O que é a sobra | É o que fica das vendas depois de pagar a comissão do Mercado Livre, o frete e o custo dos produtos informado na tela de Custos. Aluguel, salários e outras despesas também saem daí — por isso não é lucro. | `montaVeredito` e a explicação em `lib/resumo.ts` |
| 2 | O que fazer e onde ver mais | Os cartões de baixo mostram o que pede atenção agora, e cada botão abre a tela com os detalhes. As outras telas ficam no menu: Financeiro, Produtos, Clientes, Custos e Exportar. | `montaTarefas`; `components/nav/itens.ts` |

### Executive

| # | título | texto | fonte |
| --- | --- | --- | --- |
| 1 | Margem de contribuição não é lucro | É a receita menos a comissão do Mercado Livre, o frete que você pagou e o custo dos produtos. Aluguel, salários e outras despesas fixas não entram: por isso é margem, e não lucro. | nota do cartão em `app/dashboard/page.tsx` |
| 2 | Quanto da conta está completa | O custo do produto só entra quando é informado na tela de Custos. Se falta custo, um aviso abaixo dos cartões mostra quanto da receita já está coberta — e, até chegar a 100%, a margem aparece maior do que a real. | `indicador-cobertura.tsx` (some quando completa); docstring de `app/dashboard/custos/page.tsx` |
| 3 | Comparação e período | Cada cartão compara com o período anterior de mesmo tamanho. E o "Até" do seletor não inclui o próprio dia: escolher 13/10 mostra os dados até 12/10. | `janelaAnterior` em `lib/api.ts`; `CLAUDE.md` |


### Produtos

| # | título | texto | fonte |
| --- | --- | --- | --- |
| 1 | Classes A, B e C | Os produtos são ordenados por receita. A classe A soma os primeiros 80% do faturamento do período, a B vai até 95%, e a C é o restante. | `_classify` em `backend/analytics/segmentation_pg.py` |
| 2 | Quem é visto e não vende | Em Desempenho dos anúncios, cada anúncio é comparado com a mediana da própria loja. "Visto e rejeitado" pede ajuste no anúncio — preço, foto, título ou frete. "Converte, falta ser visto" pede visibilidade. | `APARENCIA` em `lib/diagnostico.ts` |
| 3 | Quando não dá para concluir | Anúncio com poucas visitas aparece como "Poucas visitas para avaliar", sem diagnóstico, para não virar alarme falso. E, em Desempenho dos anúncios, "—" quer dizer que falta dado para calcular — não é zero. | `lib/diagnostico.ts`; `desempenho-anuncios.tsx` (visita não colhida, conversão sem visita, mediana sem amostra). Restrito a esta seção de propósito: no cohort da mesma tela, "—" também marca mês sem venda, que é zero (`cohort-heatmap.tsx`) |


### Clientes

| # | título | texto | fonte |
| --- | --- | --- | --- |
| 1 | Recência, Frequência e Valor | Cada comprador recebe uma nota em três critérios: há quanto tempo comprou, quantas vezes comprou e quanto gastou. | rótulos em `buyers-table.tsx` |
| 2 | Os segmentos que pedem ação | As notas viram seis segmentos. Os que pedem atenção: "Em risco" — já foram bons compradores e estão sumindo — e "Hibernando", que provavelmente já foram embora. | `components/analytics/segmentos.ts` |
| 3 | Como ler o gráfico | Cada ponto é um comprador. Quem está embaixo à direita comprou há muito tempo e gasta pouco: é quem está indo embora. | subtítulo da Dispersão RFM em `app/dashboard/clientes/page.tsx` |

### Custos — dashboard

| # | título | texto | fonte |
| --- | --- | --- | --- |
| 1 | Por que informar o custo | O Mercado Livre não sabe quanto o produto custa para você. Sem esse número, a margem de contribuição fica maior do que a real. | docstring de `app/dashboard/custos/page.tsx` |
| 2 | E as vendas que já aconteceram | Com a opção do topo ligada, o custo salvo também vale para as vendas anteriores que estão sem custo. Um período em que você já informou um custo nunca muda: se o fornecedor subir o preço, a margem dos meses passados continua a mesma. | `gravar_custo` e `VIGENCIA_DO_HISTORICO` em `backend/analytics/custos_pg.py`; `docs/specs/2026-10-28-custo-retroativo-design.md`. Reescrito em 2026-10-28 (antes: "O custo vale daqui para frente") |
| 3 | Por onde começar | Comece pelos produtos que mais faturam: são eles que mais mexem na margem. | — (orientação, não afirmação sobre o produto) |

### Custos — demo

| # | título | texto | fonte |
| --- | --- | --- | --- |
| 1 | O custo que só o vendedor sabe | Aqui o vendedor informa quanto cada produto custa para ele — o único número que o Mercado Livre não tem. Sem ele, a margem fica maior do que a real. | docstring de Custos |
| 2 | Nesta demonstração | A tabela é só leitura. Alguns produtos estão sem custo de propósito, para você ver como as outras telas avisam quando a margem está incompleta. | docstring de `app/demo/custos/page.tsx` |

### Exportar

| # | título | texto | fonte |
| --- | --- | --- | --- |
| 1 | Leve os números para a planilha | Cada tabela sai num arquivo CSV. Dá para baixar uma de cada vez ou todas de uma vez — e, mesmo assim, cada uma vem no seu próprio arquivo. | `painel-exportacao.tsx` ("São N arquivos separados, um por tabela") |
| 2 | Abre direto no Excel | O arquivo já vem no formato do Excel em português: ponto e vírgula entre colunas, vírgula nos decimais e acentos preservados. Nesta tela há um glossário explicando cada coluna. | `lib/csv.ts`; `glossario-colunas.tsx` |

## 5. Arquitetura

Três unidades, cada uma com um papel.

**`frontend/lib/tutoriais.ts` — o conteúdo e as regras, sem React.**

```ts
type ChaveDeTutorial = "executive" | "produtos" | "clientes" | "custos" | "exportar";
type Contexto = "demo" | "dashboard";
type Slide = { titulo: string; texto: string };
type Tutorial = { versao: number; slides: Slide[]; slidesDaDemo?: Slide[] };

export const TUTORIAIS: Record<ChaveDeTutorial, Tutorial>;
export function slidesDoContexto(tutorial: Tutorial, contexto: Contexto): Slide[];
export function chaveDeArmazenamento(contexto: Contexto, tela: ChaveDeTutorial, versao: number): string;
export function deveAbrirSozinho(estado: {
  jaVisto: boolean;
  temDados: boolean;
  armazenamentoDisponivel: boolean;
}): boolean;
```

Funções puras, testáveis no vitest sem montar componente — o front deste
projeto não testa componentes, então a lógica que importa mora fora deles.

**`frontend/components/analytics/tutorial-da-tela.tsx` — o modal.**
Client Component. Recebe `tela` (texto) e `temDados` (booleano) — dado puro,
então atravessa a fronteira RSC. Deriva o contexto de `usePathname()`
(`/demo` ou não). Renderiza o botão "Como usar esta tela" e o `<dialog>`
nativo, aberto com `showModal()`: foco preso, ESC e a camada superior do
navegador vêm de graça, sem dependência nova e sem disputar z-index com a
gaveta de navegação.

O `localStorage` é lido num `useEffect`, depois de montar. Ler durante a
renderização daria uma resposta no servidor (sem `localStorage`) e outra no
navegador — erro de hidratação. Toda leitura e escrita vai em `try/catch`.

**`CabecalhoDeTela` ganha duas props**, `tela` e `temDados`, e renderiza o
`TutorialDaTela`. As dez páginas passam as duas; `temDados` sai do que a
página já calcula:

| tela | `temDados` |
| --- | --- |
| Executive | `!erro && fluxo.length > 0` |
| Produtos | `!erro && abc.length > 0` |
| Clientes | `!erro && rfm.length > 0` |
| Custos | `!erro && linhas.length > 0` |
| Exportar | `!erro && fluxo.length + abc.length + rfm.length > 0` |

**Antes de escrever o código:** `frontend/AGENTS.md` avisa que esta versão do
Next.js tem mudanças incompatíveis — ler o guia em `node_modules/next/dist/docs/`
antes de usar `usePathname` ou qualquer API do framework.

## 6. Acessibilidade

- `<dialog>` com `aria-labelledby` apontando para o título do slide.
- ✕ com `aria-label="Fechar tutorial"`; botão "?" com rótulo visível.
- Progresso anunciado em texto ("Passo 2 de 3"), não só nos pontos.
- Foco no botão primário ao abrir; ao fechar, volta ao elemento de antes.
- Alvos de toque de pelo menos 44px no celular.
- Transição desligada com `prefers-reduced-motion`.

## 7. Verificação

**Testes (vitest), em `lib/tutoriais.test.ts`:**
- toda tela tem de 1 a 3 slides, nos dois contextos;
- nenhum título ou texto vazio, e nenhum texto acima de 260 caracteres (cabe
  no celular sem rolar);
- `slidesDoContexto` usa `slidesDaDemo` quando existe, e `slides` quando não;
- formato da chave de armazenamento;
- tabela-verdade de `deveAbrirSozinho` — validada por mutação: inverter a
  condição de `temDados` tem que derrubar o teste.

**Navegador, em `/demo` com o banco de teste semeado:** abre sozinho na
primeira visita; Próximo, Voltar e Entendi; ✕, ESC e clique fora; recarregar
não reabre; o "?" reabre; limpar o `localStorage` reabre; 390px de largura;
console limpo; nada aparece em `/`.

**Revisão:** `revisor-de-interface` contra esta spec — a primeira vez que ele
roda numa tarefa real.

**Dashboard:** exige login, que eu não faço. Vai por PR com preview da Vercel;
o dono do produto confere as cinco telas logado antes do merge.

**Entrega:** o `verificador-de-entrega` confirma o deploy de produção com um
marcador do código novo — as duas plataformas já falharam em silêncio.

## 8. Fora de escopo

Tour com destaque nos elementos, vídeo ou GIF, métricas de quem pulou (o
projeto não tem analytics), guardar no banco, tutorial em
`/dashboard/conectar` e na vitrine.

## 9. Achados no caminho

Dois problemas encontrados ao escrever o conteúdo, fora do escopo desta
feature e registrados para decisão:

**O custo informado não cobre vendas passadas — e isso vai parecer bug.**
Por desenho (`metrics_pg.py`), venda anterior à primeira vigência fica sem
custo. Um vendedor novo que informa todos os custos hoje volta ao Executive e
vê a margem dos últimos 90 dias igual, com a cobertura baixa. O slide 2 de
Custos explica; a correção de verdade seria permitir uma vigência retroativa,
que a docstring de Custos chama de "outra tela, e por ora não existe".

A própria tela de Custos piorava isso: com o catálogo todo preenchido, dizia
"a margem já desconta o custo dos produtos" — falso para as vendas passadas.
Corrigido nesta branch, porque o tutorial punha as duas frases lado a lado.

**A vitrine afirma algo que o produto não faz.** A seção "Da análise à ação"
diz que o vendedor informa o custo "com a data em que aquele custo passou a
valer". O vendedor não escolhe data: o custo vale de hoje em diante.
Corrigido em 2026-10-27: o texto passou a dizer que cada venda nova desconta
o custo, e deixou de chamar a margem de "o que sobra mesmo, no bolso".

**Da revisão, já existiam antes desta branch:**

- Texto branco no botão laranja (`--sp-accent`, `#ea580c`) dá 3,56:1, abaixo
  dos 4,5:1 que texto de 14px pede — e o comentário de `globals.css` afirma
  "≥ 4.5:1". Vale para todo botão principal do produto. Corrigido em
  2026-10-23, por decisão do dono: o accent passou a `#c2410c` (5,18:1). O
  herói, de fundo escuro, ganhou um token próprio com o tom antigo, porque lá
  o novo cairia para 2,18:1.
- A legenda do cohort dizia "sem venda possível (antes do lançamento)", mas a
  mesma célula tracejada marca mês posterior ao lançamento sem venda.
  Corrigido à parte, em `62a8ce6`.
- Os cartões do Executive mostravam a variação com ponto ("+1.1%"), por
  `toFixed(1)` em `kpi-card.tsx`. Corrigido à parte, em `7c200dc`.
