# Identidade visual do dashboard — Fase 2.5 (v0.3.1)

**Data:** 2026-08-25
**Status:** aprovado, pronto para plano de implementação
**Escopo:** estilização da interface Streamlit. Nenhuma métrica, query ou regra de negócio é alterada.

## Problema

O dashboard roda hoje no tema dark padrão do Streamlit: sem CSS próprio, com a
paleta categórica default do Plotly (vermelho e verde saturados), `st.metric`
cru e nenhuma moldura entre as seções. A home é apenas um título e a frase
"Selecione uma página na barra lateral".

O SellerPulse é peça de portfólio para vagas de BI. A camada analítica está
pronta e correta; a apresentação não comunica isso. Além disso, o relatório PDF
gerado por `templates/relatorio.html.j2` tem identidade visual própria
(navy/gold, Inter) que o dashboard ignora — os dois não parecem o mesmo produto.

## Decisões

Fixadas no brainstorm de 2026-08-25 e **não devem ser re-litigadas**:

1. **Paleta:** navy/gold do PDF transposta para fundo escuro. Corporativa e
   sóbria — sem neon, sem glow.
2. **Layout:** herda a *estrutura* da referência visual (tiles de KPI com ícone,
   cada seção num cartão, grid de 2 colunas, faixa de resumo no topo), não a
   sua paleta.
3. **Onde mora o estilo:** um módulo `src/theme.py` mais um `.streamlit/config.toml`.
   Páginas nunca escrevem CSS. Sem dependências novas.
4. **KPIs:** `st.metric` sai; entram tiles HTML com ícone, valor, rótulo em
   caixa alta e pílula de variação.
5. **Escopo:** fundação mais as quatro telas (home, Executive, Products, Customers).
6. **Versão:** 0.3.1, branch `feat/ui-theme`. O `v0.4.0` fica reservado para a
   Fase 3 (OAuth), cujo spec já existe.

## Paleta e tokens

Definidos em `COLORS` no `src/theme.py`. A coluna "origem" aponta a variável
correspondente em `templates/relatorio.html.j2`, para manter dashboard e PDF
alinhados.

| Papel | Token | Valor | Origem |
|---|---|---|---|
| Fundo da página | `bg` | `#051431` | `--navy-950` |
| Superfície (cards) | `surface` | `#0a1f3d` | `--navy-900` |
| Superfície elevada (tiles) | `surface_raised` | `#0f2a4d` | interpolado |
| Borda | `border` | `rgba(148,163,184,.14)` | derivado de `--gray-400` |
| Texto primário | `text` | `#e8eef7` | novo (dark) |
| Texto secundário | `text_muted` | `#8fa3bf` | novo (dark) |
| Acento primário | `accent` | `#3b82f6` | `--blue-500` |
| Acento secundário | `gold` | `#c9a961` | `--gold-500` |
| Positivo | `positive` | `#34d399` | `--positive` clareado |
| Negativo | `negative` | `#f87171` | `--negative` clareado |

**Rampa categórica dos gráficos**, nesta ordem exata:
`#3b82f6`, `#c9a961`, `#60a5fa`, `#94a3b8`, `#34d399`, `#f87171`.

**Escala contínua** (heatmap de cohort), com estes três pontos de parada:
`#0a1f3d` (0%) → `#3b82f6` (60%) → `#c9a961` (100%).

**Ícones dos tiles:** SVG inline monocromático, na cor `accent`, com stroke de
1.5px e 20px de lado. Definidos como um dicionário `ICONS: dict[str, str]` no
`theme.py`; o campo `Kpi.icon` guarda a chave desse dicionário. Emoji está
descartado — destoa da regra de contenção corporativa.

Os contrastes devem ser validados contra as regras da skill `dataviz` durante a
implementação, antes de fixar a rampa em código.

**Tipografia:** Inter (mesma do PDF), carregada via Google Fonts com stack de
fallback `Inter, system-ui, -apple-system, sans-serif`. KPIs usam
`font-feature-settings: "tnum"` para que os dígitos não mudem de largura.

**Regras de contenção — "corporativo sem poluição":**

- Nenhum `box-shadow` colorido, nenhum efeito de glow, nenhum gradiente em texto.
- Profundidade vem apenas de superfície mais clara mais borda de 1px.
- Raio de borda uniforme: 12px.
- Caixa alta com `letter-spacing` só nos rótulos de KPI.

## Arquitetura

Dois arquivos novos. Nenhuma dependência nova.

### `.streamlit/config.toml`

Define apenas o que o Streamlit precisa saber por conta própria: cor de fundo,
cor de texto, cor primária e fonte base. Isso garante que widgets nativos não
estilizados já nasçam na paleta certa e elimina o flash de tela branca no
carregamento inicial.

### `src/theme.py`

Estimativa: cerca de 180 linhas. Este é o contrato completo que as páginas
enxergam:

Convenção do módulo: funções `*_html` constroem string e não tocam o Streamlit —
são elas que os testes exercitam. As demais renderizam. Essa separação é o que
torna o módulo testável sem runtime do Streamlit.

```python
COLORS: dict[str, str]
CHART_SEQUENCE: list[str]
CHART_CONTINUOUS: list[list]
GRID_COLOR: str
FONT_STACK: str
ICONS: dict[str, str]          # nome -> miolo do SVG

@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    icon: str                  # chave de ICONS
    delta: str | None = None
    delta_positive: bool | None = None

def icon_html(name: str, size: int = 20, color: str | None = None) -> str
def build_css() -> str
def inject_css() -> None
def page_header_html(title: str, subtitle: str | None = None, period: str | None = None) -> str
def page_header(title: str, subtitle: str | None = None, period: str | None = None) -> None
def kpi_row_html(kpis: list[Kpi]) -> str
def kpi_row(kpis: list[Kpi]) -> None
def card(title: str, subtitle: str | None = None) -> AbstractContextManager
def style_fig(fig: go.Figure) -> go.Figure
def nav_card(title: str, description: str, icon: str, page: str) -> None
```

Semântica de cada função:

- **`build_css()` / `inject_css()`** — `build_css` devolve a folha de estilo como
  string (é o que os testes verificam); `inject_css` a emite num bloco `<style>`.
  Convenção: chamar `inject_css()` uma vez, no topo de cada página. Chamar duas
  vezes no mesmo run apenas emite um segundo bloco idêntico — inofensivo, já que
  as regras são as mesmas, mas desnecessário.
- **`page_header()`** — título, subtítulo opcional e o período ativo como pílula.
  Substitui os pares `st.title` mais `st.caption` das páginas atuais.
- **`kpi_row()`** — renderiza a lista inteira de tiles em CSS Grid.
- **`card()`** — context manager usado como `with card("Título"): st.plotly_chart(...)`.
- **`style_fig()`** — aplica fundo transparente, cor de grade, tipografia,
  legenda e hover a uma figura Plotly. Devolve a própria figura. **Ressalva:**
  `colorway` só afeta traces sem cor explícita, e figuras do Plotly Express já
  nascem com cor por trace — para elas, a rampa precisa ser passada como
  `color_discrete_sequence=CHART_SEQUENCE` na criação da figura.
- **`nav_card()`** — usado apenas na home; envolve um `st.page_link` clicável. O
  parâmetro `page` recebe o caminho do arquivo da página relativo à raiz do
  projeto (por exemplo `"src/pages/1_executive.py"`), que é o formato aceito
  pelo `st.page_link`.

### Restrições técnicas do Streamlit

Duas limitações moldam o desenho acima. Registradas aqui para não serem
redescobertas na implementação:

1. **HTML cru não embrulha widgets.** Um `st.markdown("<div>")` não envolve o
   `st.plotly_chart` que vem depois. Por isso `card()` é um context manager
   sobre `st.container(border=True)`, estilizado via CSS no
   `[data-testid="stVerticalBlockBorderWrapper"]`. Já `kpi_row()` não contém
   widget algum, então é HTML puro — e precisa ser emitido numa **única**
   chamada de `st.markdown`, senão aparecem espaçamentos fantasma entre as
   colunas.
2. **Atributos `data-testid` mudam entre versões do Streamlit.** Mitigação:
   fixar `streamlit>=1.62,<2` no `requirements.txt` e concentrar todo seletor
   frágil num bloco único e comentado no topo do `theme.py`, de modo que uma
   quebra de versão tenha um só lugar a consertar.

## As quatro telas

Nenhuma tela ganha métrica nova, query nova ou dado novo. `src/metrics.py` e
`src/segmentation.py` não são tocados.

### Sidebar — `src/dashboard.py`

Bloco de marca no topo (wordmark "SellerPulse" com a versão discreta abaixo),
filtros de período agrupados num cartão, seletor Demo/Real e seletor de
categoria preservados exatamente como estão funcionalmente — inclusive o guard
de `sidebar_modo` que roda antes da instanciação do widget.

### Home — `src/dashboard.py`

Substitui as três linhas de texto atuais por uma capa: wordmark grande, a linha
de posicionamento "Analytics para vendedores Mercado Livre", o período ativo em
pílula e três cartões de navegação lado a lado (Executive, Products, Customers),
cada um com ícone, título e uma frase do que a tela entrega. Navegação real via
`st.page_link` dentro do cartão.

### Executive — `src/pages/1_executive.py`

Cabeçalho, faixa de 4 tiles (Receita bruta, Custo total, Lucro líquido, Nível
ML) e um cartão único com o fluxo financeiro por dia.

**Mudança de conteúdo:** hoje a tela exibe "Receita bruta" duas vezes — no KPI e
de novo na seção "Comparativo com janela anterior", que só acrescenta a variação
percentual. As duas se fundem: a variação passa a ser a pílula de delta dentro
do próprio tile. A seção "Comparativo" deixa de existir como bloco visual; o
cálculo de `_render_comparativo` é **preservado** e passa a alimentar os campos
`delta` e `delta_positive` dos tiles. Nenhuma informação é perdida.

### Products — `src/pages/2_products.py`

Cabeçalho; grid de 2 colunas com Top produtos e Top categorias em cartões lado a
lado; Pareto ABC em cartão de largura total, com a contagem A/B/C como rodapé do
próprio cartão; heatmap de cohort em cartão abaixo.

As tabelas ganham `column_config` para formatar valores em reais e contagens —
hoje são exibidas cruas. O `fig.update_layout` manual do Pareto sai, substituído
por `style_fig` mais os ajustes de eixo secundário, que são específicos daquele
gráfico e permanecem locais.

### Customers — `src/pages/3_customers.py`

Cabeçalho; faixa de 4 tiles (Compradores únicos, Champions, At Risk, Ticket
médio); abaixo, grid de 2/3 mais 1/3 com o scatter RFM no cartão largo e a
distribuição por segmento no estreito. Hoje esses dois gráficos consomem duas
telas inteiras de rolagem.

## Testes

Os três smoke tests de `tests/test_dashboard.py` permanecem sem alteração e
seguem sendo a rede de segurança principal: eles verificam que cada página
carrega sem exceção, que é exatamente o que pode quebrar quando as páginas
passam a chamar helpers do `theme`.

Novo arquivo `tests/test_theme.py`, com testes unitários puros (sem Streamlit em
execução) sobre o contrato do módulo:

- `COLORS` contém todos os tokens da tabela acima.
- `CHART_SEQUENCE` tem os seis valores, na ordem especificada.
- `kpi_row_html` emite HTML contendo o valor e o rótulo de cada `Kpi` recebido.
- Um `Kpi` com `delta_positive=True` e outro com `False` produzem cores
  distintas de pílula.
- `style_fig` aplica o fundo transparente, a cor de grade e o `colorway` ao `go.Figure`.
- `card` devolve um objeto que implementa o protocolo de context manager.

`src/theme.py` não entra na lista `omit` de `[tool.coverage.run]` no
`pyproject.toml` — é o único arquivo novo com lógica de verdade e deve ser
coberto.

## Riscos

| Risco | Mitigação |
|---|---|
| Seletores CSS quebram numa atualização do Streamlit | Fixar `streamlit>=1.62,<2`; isolar todo seletor por `data-testid` num bloco único e comentado no topo do `theme.py` |
| Google Fonts indisponível (offline) | Stack de fallback `system-ui`; a tela degrada para a fonte do sistema sem quebrar layout |
| `AppTest` não renderiza CSS, então nenhum teste pega regressão visual | Verificação manual, registrada pela atualização dos prints em `docs/img/` |

## Entrega

Branch `feat/ui-theme`, versão 0.3.1.

Ordem de implementação — as páginas só começam depois que a fundação passar nos
testes:

1. Fundação: `.streamlit/config.toml`, `src/theme.py`, `tests/test_theme.py`,
   pin do Streamlit no `requirements.txt`
2. Executive, como piloto do visual
3. Home
4. Products
5. Customers
6. Prints em `docs/img/` atualizados e README revisado

## Fora de escopo

- Qualquer alteração em `src/metrics.py` ou `src/segmentation.py`
- Métricas, gráficos ou filtros novos
- Restilização do PDF (`templates/relatorio.html.j2`) — ele já tem identidade
- Tema claro; o dashboard é dark-only
- OAuth e o toggle Demo/Real funcional — são a Fase 3 (v0.4.0)
