# SellerPulse — Sprint 3: Telas de análise e vitrine

**Sprint:** 3 de 4 da migração pra SaaS real
**Data:** 2026-09-28
**Status:** Design aprovado — implementação pendente.

---

## 1. Contexto

As Sprints 1 e 2 construíram tudo que não aparece: autenticação multi-tenant, schema isolado por seller, OAuth do Mercado Livre com tokens cifrados, fila de ingestão com worker, e a camada analítica inteira portada pra Postgres. São 176 testes no backend.

O problema é que **nada disso é visível**. Hoje, quem abre o site cai numa tela de login. O dashboard tem uma página só. A demonstração existe como endpoint e não como tela. O Streamlit antigo saiu do ar.

Esta sprint fecha esse vão, e a ordem importa: primeiro o produto existe, depois ele é mostrado. Construir a vitrine antes das telas significaria fotografar algo que ainda não está lá.

**Decisão explícita do Guilherme (2026-09-28):** a raiz do site passa a ser uma **vitrine**, não o login. A conta vem como consequência de a pessoa gostar do produto, então a página precisa de vários pontos de cadastro conforme a rolagem. O login fica discreto no topo, para quem já é usuário.

Referência visual: `adstart.com.br` — herói com CTA, problema/solução, como funciona, e CTA repetido ao longo da rolagem.

## 2. Goals & non-goals

### Goals

- Página **Produtos**: curva ABC de Pareto e cohort de produto, respondendo "quais produtos sustentam o faturamento".
- Página **Clientes**: dispersão e segmentação RFM, respondendo "quem compra de novo e quem sumiu".
- **Demonstração pública navegável**: as três telas acessíveis sem cadastro, em `/demo`.
- **Landing page na raiz do site**, com vídeo no herói, quatro pontos de cadastro na rolagem, e o foco em Mercado Livre comunicado de forma sutil desde o topo.
- Navegação entre as três páginas do dashboard.

### Non-goals

- **Relatório PDF embutido** — Sprint 4.
- **Novos endpoints ou queries analíticas.** Os cinco endpoints já existem e estão testados desde a Sprint 1. Esta sprint é de consumo, não de produção de dados. Se alguma tela precisar de dado que não existe, isso é um achado a reportar, não a implementar por conta.
- **Billing, planos, preços.** A landing fala "grátis" porque é, não porque existe um plano pago escondido.
- **Blog, newsletter, depoimentos.** Ver decisão 3.
- **Responsividade a partir de tablet pra baixo no dashboard.** A landing é responsiva de verdade (é onde chega tráfego frio); o dashboard continua desktop-first como na Sprint 1.

## 3. Decisões travadas

| # | Decisão | Escolha | Alternativas preteridas |
|---|---|---|---|
| 1 | Ordem da sprint | **Telas → demo → landing.** A vitrine abre no fim, com o produto inteiro atrás | Landing primeiro (fecharia o vão antes, mas com print de tela inexistente, e a landing seria refeita) |
| 2 | Raiz do site | **Landing page.** Login vira link discreto no topo | Manter o redirecionamento pra `/login` |
| 3 | Prova social | **Nenhuma inventada.** No lugar dela, a demonstração navegável | Números e depoimentos fictícios no estilo da referência |
| 4 | Biblioteca de gráficos | **Recharts** para Pareto e dispersão RFM; heatmap do cohort em grid CSS | SVG na mão pros três (a Sprint 1 já previa que a lib se pagaria aqui); nivo/visx (mais peso, sem ganho) |
| 5 | Foco no Mercado Livre | **Enquadrado como especialidade, não como limite** — linha discreta acima do título, e uma seção que trata isso como vantagem | Selo "só Mercado Livre" (lê-se como limitação) |
| 6 | Vídeo do herói | **Arquivo `12647214_1920_1080_30fps.mp4`** (anexado pelo Guilherme, 13MB, 1920×1080 a 30fps). Imagem de fundo primeiro, vídeo por cima quando carregar | Outro vídeo; vídeo bloqueando a renderização (13MB trava a página em 4G) |

### Justificativa da decisão 3

A referência (`adstart.com.br`) tira boa parte da força de prova social: "+2000 agências", "+R$ 16,5B em faturamento", depoimentos assinados, 35 integrações. O SellerPulse não tem nada disso, e inventar está fora de questão — além de desonesto, é o tipo de coisa que quem avalia tecnicamente percebe.

A troca é favorável. Onde a referência diz "35 integrações", a resposta aqui é **"feito para o Mercado Livre"**: uma ferramenta que só precisa entender uma plataforma já traz taxa, frete e cancelamento calculados, sem configuração. E onde a referência põe depoimento, esta página põe **o produto rodando** — a demonstração navegável convence mais que qualquer citação, porque a pessoa usa antes de decidir.

### Justificativa da decisão 6

O arquivo tem 13MB. Como vídeo de herói bloqueando a primeira renderização, isso é meio minuto de tela branca numa conexão móvel — a pessoa vai embora antes de ver a frase. O herói é construído com um poster estático, e o vídeo entra por cima quando termina de carregar; em conexão lenta ou com `prefers-reduced-motion`, ele simplesmente não entra e a página continua correta.

A compressão pra 2–3MB depende do `ffmpeg`, que não está instalado na máquina. **A landing não fica bloqueada por isso** — sobe com o poster e ganha o vídeo depois.

## 4. As telas

### 4.1 Produtos (`/dashboard/produtos`)

Responde: *quais produtos sustentam o faturamento, e quais só ocupam espaço.*

- **Curva ABC de Pareto** (`GET /segmentation/abc`). Barras de receita por produto em ordem decrescente, com a linha de percentual acumulado sobreposta e marcações em 80% e 95%. É o gráfico que torna a regra 80/20 visível em vez de afirmada.
- **Três cartões de classe** — quantos produtos e quanta receita em A, B e C. A leitura que importa é a desproporção: poucos produtos, muita receita.
- **Tabela por produto** — `sku`, `titulo`, `receita`, `receita_pct`, `receita_acumulada_pct`, `classe`, com a classe como etiqueta colorida.
- **Heatmap de cohort** (`GET /segmentation/cohort`) — receita por mês de lançamento contra mês corrente. Mostra se produto novo sustenta receita ou só dá pico de lançamento.

### 4.2 Clientes (`/dashboard/clientes`)

Responde: *quem compra de novo, quem está sumindo, e quanto isso vale.*

- **Dispersão RFM** (`GET /segmentation/rfm`) — recência no eixo X, valor no Y, frequência no tamanho do ponto, segmento na cor. Quem está no canto errado do gráfico é quem está indo embora.
- **Faixa de segmentos** — contagem e receita por `Champions`, `Loyal`, `At Risk`, `New`, `Hibernating`, `Others`, com uma frase em português explicando o que cada um significa. Os rótulos vêm em inglês do `src/segmentation.py` (código congelado da Fase 2); a tela traduz na exibição sem mexer no dado.
- **Tabela por comprador**, ordenável, com os três scores e o segmento.

### 4.3 Navegação

O `dashboard/layout.tsx` ganha navegação entre Executive, Produtos, Clientes e Conectar conta, marcando a ativa.

## 5. A demonstração pública (`/demo`)

As mesmas três telas, sem autenticação, servidas pelos endpoints `/demo/*`.

**O que isto exige do backend:** hoje só existem `/demo/fluxo-financeiro` e `/demo/top-produtos`. As telas de Produtos e Clientes precisam de `/demo/abc`, `/demo/rfm` e `/demo/cohort` — mesma forma dos existentes: só GET, `seller_id` resolvido no servidor, `is_demo` verificado, `Cache-Control` público. É a única adição de backend desta sprint, e é replicação de um padrão já testado.

Um aviso discreto e permanente no topo: são dados de demonstração, não uma loja real.

## 6. A landing (`/`)

Sete seções. Quatro pontos de cadastro: herói, depois das análises, depois do foco em ML, e a faixa final.

| # | Seção | Conteúdo | CTA |
|---|---|---|---|
| 1 | Herói | Vídeo de fundo, frase central, dois botões: criar conta e ver demonstração. Acima do título, a linha discreta que marca o foco em Mercado Livre | ✅ |
| 2 | O problema | Planilha no fim do mês não diz qual produto dá lucro nem qual cliente sumiu | |
| 3 | As três análises | Prints reais das telas, cada um com a pergunta que responde | ✅ |
| 4 | Como funciona | Criar conta → conectar o ML → os 6 meses entram sozinhos | |
| 5 | Feito para o Mercado Livre | Taxa, frete e cancelamento já entram na conta. Foco tratado como vantagem | ✅ |
| 6 | Seus dados | Token criptografado, isolamento por conta, desconectar quando quiser | |
| 7 | Faixa final | Grátis, sem cartão | ✅ |

O cabeçalho tem o logo, "Ver demonstração" e um "Entrar" discreto. Quem já tem sessão vê "Ir pro dashboard" no lugar.

**A raiz deixa de redirecionar.** Usuário logado que abre `/` vê a landing com o atalho pro dashboard, não um salto automático — quem digitou o domínio quis ver a página.

## 7. Testes

O frontend não tem suíte, e criar uma do zero é sprint própria. A verificação aqui é:

- `npm run lint` e `npm run build` limpos, incluindo checagem de tipos.
- Os endpoints novos de demo entram na suíte do backend, com os mesmos testes que os existentes já têm: responde sem auth, ignora `seller_id` do cliente, recusa seller não marcado como demo, manda `Cache-Control`.
- **Estado vazio em toda tela.** Um seller recém-conectado, ou uma janela sem vendas, não pode produzir gráfico quebrado ou `NaN`. Cada tela é verificada com a janela vazia além da janela com dados.
- Verificação visual manual das três telas contra a conta de teste já semeada.

## 8. Checkpoints

1. **Produtos e Clientes.** As duas telas, a navegação, e os gráficos. Ao final: o dashboard tem as três análises funcionando com dados reais.
2. **Demonstração pública.** Os três endpoints `/demo/*` novos e as três telas em `/demo`, sem login.
3. **Landing.** As sete seções, o herói com vídeo, a raiz apontando pra ela, e o deploy.
