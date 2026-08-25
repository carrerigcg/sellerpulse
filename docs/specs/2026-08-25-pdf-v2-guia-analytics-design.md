# SellerPulse — Fase 4: PDF v2 · Guia Analytics (v0.5.0)

**Fase:** 4 de 6 do roadmap
**Tag alvo:** `v0.5.0`
**Data:** 2026-08-25
**Status:** Design aprovado — implementação pendente.

---

## 1. Contexto

Até a Fase 3 (`v0.4.0`, em conclusão), o SellerPulse tem um gerador de PDF (`src/pdf_renderer.py` + `templates/relatorio.html.j2`) construído na Fase 1: 3 páginas A4, janela fixa de 7 dias, dados exclusivamente do `data/demo.db`. O formato é **boletim executivo** — mostra o resultado da semana com KPIs, ranking de produtos e indicadores de saúde, mas não explica o significado das métricas nem sugere ações.

Duas mudanças de contexto tornam o boletim atual insuficiente:

1. **Fase 2 (`v0.3.0`) introduziu 3 camadas analíticas** — RFM (segmentação de compradores), curva ABC (produtos por Pareto) e cohort mensal (retenção) — que nunca entraram no PDF. Elas rodam em `src/segmentation.py` e aparecem no dashboard, mas o cliente que só recebe o PDF perde essas visões.
2. **Fase 3 (`v0.4.0`) habilita OAuth no dashboard** — a partir dela, existe uma `session_conn` real com dados do vendedor conectado (6 meses de backfill), acessível via `get_active_conn()` do `dashboard_helpers.py`. O PDF pode finalmente gerar em cima de dados reais.

Esta fase troca a finalidade do PDF: deixa de ser boletim de resultados e vira **roteiro/guia analytics** — um documento que o operador (Guilherme) gera a partir da conta ML de um cliente, entrega em mãos, e o cliente pode "seguir" pra entender cada métrica e o que fazer com ela. O guia cobre as 6 famílias de métricas (financeiro + produtos + reputação + RFM + ABC + cohort), com estrutura educativa por seção e textos de ação condicionais que se adaptam à faixa do próprio número.

Design baseado em decisões travadas em sessão de brainstorm 2026-08-25 (6 perguntas de clarificação + 3 chunks de arquitetura aprovados em sequência).

## 2. Goals & non-goals

### Goals

- Gerar um PDF de **6 seções** (financeiro, top produtos, reputação, ABC, RFM, cohort) usando dados do vendedor conectado via OAuth, cobrindo os **6 meses inteiros** de backfill da Fase 3.
- Cada seção segue estrutura educativa de 3 blocos: **O que é a métrica** / **Seu resultado** / **O que você pode fazer**. Textos de ação são condicionais, escolhidos pela faixa (verde/amarelo/vermelho) do próprio resultado do vendedor.
- Botão "Baixar guia analytics (PDF)" no sidebar do dashboard, funcional apenas quando `is_ml_connected() == True` e ingestão terminou. Geração sob demanda (não pré-cachear), retorna bytes em memória via `st.download_button`.
- Refactor do template atual em partials Jinja2 modulares — 1 arquivo por seção — pra permitir manutenção paralela (outro terminal estilizando o layout, este spec adicionando conteúdo).
- Refactor do renderer em pacote `src/pdf_sections/` — 1 módulo por seção, cada um com `build_ctx()`, `FAIXAS` e `EXPLICACAO` explícitos. Renderer raiz vira orquestrador enxuto.
- CLI `gerar-pdf` continua funcional rodando contra `data/demo.db` — vira ferramenta de dev/showoff e continua alimentando os testes de golden.
- Diretriz de conteúdo travada: textos só descrevem fatos ou sugerem ações operacionais genéricas. Nada de recomendação comercial específica (preço, produto ou campanha).
- Cobertura de testes ≥ 90% nos módulos novos (padrão que a Fase 3 estabeleceu).
- Tag `v0.5.0` publicada.

### Non-goals

- **PDF P3 de patrimônio / simulação what-if** — descrito na spec `2026-08-07-camadas-analiticas-design.md` como Fase 4 tentativa. Fica pra fase futura (ou é descartado se o guia analytics cobrir a demanda).
- **LLM / geração dinâmica de texto** — textos de ação são strings estáticas em constante Python (`FAIXAS[faixa]["acoes"]`). Zero chamada de API de LLM. Escrevo eu mesmo os ~15 blocos durante a implementação.
- **Persistência de PDFs gerados** — bytes ficam em memória durante a sessão, `st.download_button` serve, o operador salva no computador dele. Nada escrito no servidor.
- **Envio automático por email / integração com CRM** — o operador entrega o PDF por fora (WhatsApp, email, in-person). Sem SMTP, sem webhook.
- **PDF interativo (links, formulários)** — WeasyPrint gera PDF/A estático. Ok pra roteiro impresso ou compartilhado.
- **i18n** — pt-BR only. Textos estáticos em português direto no código.
- **Customização por cliente / vendor branding** — mesmo template pra todos. Personalização fica pra hipotética Fase 6 (multi-tenant).
- **Geração agendada / cron** — não há cron. Cada geração é sob demanda pelo operador.
- **Comparativo entre PDFs** (ex: "guia de julho vs. guia de junho") — cada guia é standalone. O comparativo temporal já está embutido nas seções cohort e financeiro.
- **Textos condicionais opinativos sobre o negócio do cliente** — não sugerir mudar preço, escolher produto, ou definir estratégia de campanha específica. Diretriz travada (Seção 3).

## 3. Decisões travadas no brainstorm

Seis decisões resolvidas em sessão 2026-08-25. Cada uma cita a alternativa preterida.

| # | Decisão | Escolha | Alternativas preteridas |
|---|---|---|---|
| 1 | Direção da iteração | **C** — integrar com OAuth + reformular como guia educativo | A (só ampliar conteúdo); B (só redesenhar visual); D (botão download); E (email automation) |
| 2 | Escopo de métricas | **B** — 6 seções, incluindo RFM/ABC/Cohort da Fase 2 | A (só as 3 atuais); C (subset misto) |
| 3 | Formato por seção | **B** — estruturada (O que é / Seu resultado / O que fazer) | A (compacta KPI + micro-explicação) |
| 4 | Fluxo operacional | Operador (Guilherme) gera → entrega manual | Cliente self-service; envio por email; auto-geração pós-ingestão |
| 5 | Janela de dados | **B** — 6 meses inteiros do backfill | A (90 dias); C (escolha do operador) |
| 6 | Estrutura de arquivos | **B** — modularizar em partials Jinja2 + pacote `pdf_sections/` | A (arquivo único expandido de 1400 pra 3000+ linhas) |

### Diretriz de conteúdo (também travada)

Após validação com 8 exemplos de texto:

- **Podem entrar no PDF:** descrição factual da métrica, faixa considerada saudável, regras que o próprio ML aplica (penalidades/premios), ações operacionais genéricas (revisar fotos, ler reclamações, mudar foco entre aquisição e retenção).
- **Não podem entrar:** sugestões de preço específico, escolha de produto específico, decisões de campanha específica, ou qualquer texto que exija conhecer margem, categoria ou público do vendedor.

Exemplos "depende" ("campanha de reativação pra segmento At Risk", "subir estoque do produto Y") foram classificados como CRUZOU a linha e ficam de fora.

## 4. Arquitetura geral

### Módulos novos (7)

**`src/pdf_sections/`** — novo pacote Python. Um módulo por seção do PDF, cada um seguindo o mesmo contrato:

```python
# src/pdf_sections/reputacao.py (esqueleto — representa as 6 seções)

SLUG = "reputacao"

EXPLICACAO = (
    "A taxa de devolução mede quantas peças voltaram vs. quantas foram vendidas..."
)

FAIXAS = {
    "verde":    {"max": 2.0,  "acoes": ["...", "...", "..."]},
    "amarelo":  {"max": 5.0,  "acoes": ["...", "...", "..."]},
    "vermelho": {"max": float("inf"), "acoes": ["...", "...", "..."]},
}

def build_ctx(conn: sqlite3.Connection, date_from: str, date_to: str) -> dict:
    """Puro. Lê métrica via metrics.py / segmentation.py, classifica faixa,
    monta dict com valor formatado, faixa e ações condicionais."""
    ...
```

Módulos concretos (6 seções + 1 utilitário):

- `src/pdf_sections/_common.py` — helpers movidos de `pdf_renderer.py` (`_fmt_brl`, `_fmt_brl_short`, `_fmt_periodo`, `_fmt_generated_at`, `_MESES_PT`, `classificar_faixa()`).
- `src/pdf_sections/financeiro.py` — consome `metrics.fluxo_financeiro()`. Faixa = variação do mês corrente vs. média dos 5 meses anteriores.
- `src/pdf_sections/produtos.py` — consome `metrics.top_produtos()`. **Sem faixa** — puramente descritiva.
- `src/pdf_sections/reputacao.py` — consome `metrics.reputacao_devolucao()`. Faixa combina nível ML + taxa de devolução.
- `src/pdf_sections/rfm.py` — consome `segmentation.rfm()`. Faixa = % da base em segmentos leais (Champions + Loyal + Potential Loyalists).
- `src/pdf_sections/abc.py` — consome `segmentation.curva_abc()`. Faixa = % do catálogo classificado como classe A.
- `src/pdf_sections/cohort.py` — consome `segmentation.cohort_mensal()`. Faixa = retenção média em 30 dias.

**`templates/sections/`** — novo diretório. 1 partial Jinja2 por seção:

- `_layout.html.j2` — header (strip navy + gold) e footer reutilizáveis, mais os `@page` rules pro WeasyPrint. Inclui os tokens CSS num único `<style>` no `<head>`, herdados por todos os partials.
- `_financeiro.html.j2`, `_produtos.html.j2`, `_reputacao.html.j2`, `_rfm.html.j2`, `_abc.html.j2`, `_cohort.html.j2` — 1 partial por seção, cada um renderiza a estrutura "O que é / Seu resultado / O que fazer" a partir do contexto do `build_ctx()` correspondente. Nenhum partial contém tokens CSS globais — só usa as classes que o `_layout` estabelece.

### Módulos alterados (2)

**`src/pdf_renderer.py`** — reduz de ~180 linhas atuais pra ~40 linhas. Vira orquestrador enxuto:

```python
from src.pdf_sections import financeiro, produtos, reputacao, rfm, abc, cohort

SECTIONS = [financeiro, produtos, reputacao, rfm, abc, cohort]

def render_html(*, conn, date_from, date_to, generated_at=None) -> str:
    when = generated_at or datetime.now()
    ctx = {
        "periodo_label": _fmt_periodo(date_from, date_to),
        "generated_at_label": _fmt_generated_at(when),
        "secoes": [
            {"slug": s.SLUG, "ctx": s.build_ctx(conn, date_from, date_to)}
            for s in SECTIONS
        ],
    }
    return env.get_template("relatorio.html.j2").render(**ctx)


def render_pdf(
    *,
    conn: sqlite3.Connection | None = None,
    db_path: Path | None = None,
    output_path: Path | None = None,
    date_from: str,
    date_to: str,
    generated_at: datetime | None = None,
) -> bytes | Path:
    """Assinatura dual.

    - CLI passa `db_path=...` e `output_path=...` → abre a conn, escreve
      o PDF em disco, devolve o `Path`.
    - Dashboard passa `conn=...` (sem `db_path`, sem `output_path`) →
      usa a conn viva da sessão OAuth, devolve `bytes` em memória.

    Exatamente um de {conn, db_path} deve ser passado. `output_path`
    obrigatório quando `db_path` é usado, ignorado quando `conn` é usado.
    """
```

**`templates/relatorio.html.j2`** — deixa de conter o conteúdo das 3 páginas atuais. Vira casca que herda de `_layout.html.j2` e faz loop:

```jinja
{% extends "sections/_layout.html.j2" %}
{% block content %}
  {% for secao in secoes %}
    {% include "sections/_" ~ secao.slug ~ ".html.j2" %}
  {% endfor %}
{% endblock %}
```

**Coordenação com trabalho paralelo:** o outro terminal do Claude está iterando estilização em cima do `relatorio.html.j2` atual (Fase 2.5 · v0.3.1 · restyle navy/gold sem neon). A refatoração deste spec **precisa esperar** o merge da Fase 2.5 antes de quebrar em partials — a base estilizada dele vai virar o `_layout.html.j2` + tokens CSS herdados. Ordem: Fase 2.5 merge → começa esta fase.

### Módulo alterado (dashboard — 1)

**`src/dashboard.py`** — adiciona botão de download no sidebar, no bloco de "conta conectada". Aparece condicionalmente:

```python
# Simplificação — implementação real dispara render_pdf com spinner
if is_ml_connected() and st.session_state.get("ingest_done"):
    if _base_tem_vendas_suficientes(get_active_conn()):
        pdf_bytes = _generate_pdf_on_click_only()  # cachea o resultado da geração
        st.download_button(
            "Baixar guia analytics (PDF)",
            data=pdf_bytes,
            file_name=f"guia-analytics-{seller_id}-{today_yyyymmdd}.pdf",
            mime="application/pdf",
        )
    else:
        st.info("Nenhuma venda encontrada nos últimos 6 meses — guia precisa de dados.")
```

O `_generate_pdf_on_click_only` roda `render_pdf(conn=get_active_conn(), ...)` dentro de `with st.spinner("Gerando guia...")`. Bytes vivem só na sessão.

### Módulos não modificados (importante)

- `src/metrics.py`, `src/segmentation.py` — **zero mudanças**. A camada analítica pura continua indiferente à origem da conn e à finalidade do consumidor.
- `src/session_auth.py`, `src/session_store.py`, `src/ingest.py` — módulos da Fase 3 intactos. Este spec só consome via `get_active_conn()` / `is_ml_connected()`.
- `src/dashboard_helpers.py` — sem mudanças. Já expõe `get_active_conn()` e `is_ml_connected()` que este spec precisa.
- `src/main.py` — CLI `gerar-pdf` intacto. Continua chamando `render_pdf(db_path=..., output_path=...)`. O renderer com assinatura dual atende os 2 callers.

## 5. Contrato de cada seção

Todo módulo em `src/pdf_sections/<nome>.py` expõe **exatamente 4 símbolos**:

1. `SLUG: str` — string curta (ex: `"reputacao"`), usada pelo `render_html` no `{% include %}` dinâmico e como identificador de fixture nos testes.
2. `EXPLICACAO: str` — texto do bloco "O que é" da seção. Fixo, não muda por vendedor.
3. `FAIXAS: dict[str, dict]` — dict com 3 chaves (`"verde"`, `"amarelo"`, `"vermelho"`), cada valor tem `"max": float` (limite superior exclusivo da faixa) e `"acoes": list[str]` (lista de bullets pro bloco "O que fazer").
4. `build_ctx(conn, date_from, date_to) -> dict` — função pura que lê a métrica, classifica faixa via `_common.classificar_faixa()`, e devolve dict com os campos esperados pelo partial correspondente.

### Contrato do dict devolvido por `build_ctx()`

Campos comuns (todas as seções):

- `explicacao: str` — vem de `EXPLICACAO` (facilitando templates dumb).
- `faixa: str` — `"verde"`, `"amarelo"` ou `"vermelho"` (ou `None` pra seções sem faixa como Produtos).
- `acoes: list[str]` — vem de `FAIXAS[faixa]["acoes"]` (ou `[]` se `faixa is None`).
- `resultado: dict` — subdict com o(s) número(s) principal(is) formatado(s) pro bloco "Seu resultado". Estrutura varia por seção.

Campos extras específicos de cada seção — documentados no docstring do respectivo `build_ctx()`.

### Contrato `classificar_faixa()`

```python
# src/pdf_sections/_common.py

def classificar_faixa(valor: float, faixas: dict[str, dict]) -> str:
    """Devolve 'verde', 'amarelo' ou 'vermelho' baseado no valor e nos
    limites em FAIXAS.

    Semântica dos limites: 'max' é EXCLUSIVO. Ex: FAIXAS['verde']['max'] = 2.0
    significa que valor < 2.0 cai em verde.
    Faixas devem estar ordenadas por max crescente. Vermelho normalmente
    tem max = float('inf').

    Raises: ValueError se valor não cair em nenhuma faixa (indica FAIXAS
    mal-formada, não erro do dado)."""
```

## 6. Sequência das seções e faixas propostas

Ordem no PDF (narrativa macro → detalhe → comportamento):

| Ordem | Seção | Métrica que dispatch a faixa | Verde | Amarelo | Vermelho |
|-------|-------|------------------------------|-------|---------|----------|
| 1 | Financeiro | variação do líquido do mês corrente vs. média dos 5 meses anteriores | > 0% | −10% a 0% | < −10% |
| 2 | Reputação & Devoluções | nível ML + taxa devolução como sub-indicador | Verde ML **e** devol < 2% | Amarelo ML **ou** devol 2–5% | Vermelho ML **ou** devol > 5% |
| 3 | Top Produtos & Categorias | — (sem faixa; puramente descritiva) | — | — | — |
| 4 | Curva ABC | % do catálogo classificado como classe A (80% da receita) | > 20% (diversificado) | 10–20% (concentração normal) | < 10% (alta concentração) |
| 5 | RFM | % da base em Champions + Loyal + Potential Loyalists | > 40% | 20–40% | < 20% |
| 6 | Cohort mensal | retenção média em 30 dias | > 20% | 10–20% | < 10% |

Thresholds são propostas iniciais baseadas em heurísticas de mercado; ficam no código como constantes e podem ser ajustados por PR direto no arquivo da seção sem tocar em `pdf_renderer.py` nem em templates. Cada ajuste de threshold requer atualizar o golden HTML correspondente.

## 7. Diretriz de conteúdo dos textos

Regra travada:

> Textos podem **descrever fatos** (o que a métrica é, faixa saudável, o que o ML restringe ou premia) e **sugerir ações operacionais genéricas** (revisar fotos, ler reclamações, mudar foco entre aquisição/retenção). NÃO podem sugerir **decisões comerciais específicas** (preço, produto ou campanha específica) porque exigiria conhecer margem, categoria e público do vendedor — informações que o PDF não tem.

### Exemplos validados

| ✅ OK | ❌ CRUZOU |
|-------|-----------|
| "Revisar fotos e medidas dos anúncios mais devolvidos" | "Diminuir o preço do produto XYZ pra girar estoque parado" |
| "20% dos seus produtos respondem por 80% da receita — perder um deles concentra risco" | "Sua margem está baixa — provavelmente você tá vendendo com preço abaixo do mercado" |
| "Nenhum comprador voltou depois de 60 dias — indica dependência de aquisição nova" | "Considere subir o estoque do produto Y — vem crescendo há 3 semanas" |
| "Reputação amarela: taxa acima de 3%. ML restringe alcance nesse patamar" | "Compradores 'At Risk' já foram VIP — vale considerar campanha de reativação" |

### Volume estimado

5 seções × 3 faixas × ~4 bullets por faixa = **~60 bullets** de ações condicionais a escrever. Mais 6 blocos de `EXPLICACAO` (~2-3 frases cada). Escrita durante a implementação, dentro de cada task de seção.

## 8. Integração com o dashboard

### Onde o botão aparece

Sidebar do dashboard, no bloco de "conta conectada" (que já existe da Fase 3). Fica **logo acima** do link de "Desconectar conta". Só aparece quando **todas** essas condições são verdadeiras:

- `is_ml_connected() == True` (session_conn viva + tokens presentes)
- `st.session_state.get("ingest_done") == True` (backfill terminou; flag já existe da Fase 3)
- `_base_tem_vendas_suficientes(conn)` retorna `True` (pelo menos 1 pedido no período de 6 meses)

Se a base está vazia (última condição falha), mostra `st.info("Nenhuma venda encontrada nos últimos 6 meses — guia precisa de dados.")` no lugar do botão.

### Fluxo do click

1. Click no `st.download_button` dispara re-execução do script.
2. Antes do download_button ser desenhado, dentro de `with st.spinner("Gerando guia..."):` o `render_pdf(conn=get_active_conn(), date_from=..., date_to=...)` roda e devolve `bytes`.
3. Bytes são passados como `data=` pro `st.download_button` que serve com filename `guia-analytics-{seller_id}-{yyyymmdd}.pdf`.
4. Log estruturado no console: `seller_id`, tempo de geração em ms, tamanho em KB. Facilita debug e observação de tempo típico em produção.
5. Bytes não são cacheados entre reruns — cada click regera. Aceitável dado que uso típico é 1-2 gerações por sessão de operador.

### Loading state

WeasyPrint tipicamente leva 5-15s em máquina modesta (parte do custo é fetch das fontes Inter via `@font-face`; parte é o layout engine). `st.spinner` cobre. Se passar de 30s, avaliar em backlog: pré-download das fontes no Docker do Streamlit Cloud, ou fallback pra `system-ui`.

### Janela

Sempre 6 meses fechados: `date_to = today.isoformat()`, `date_from = (today - 6 meses corridos).isoformat()`. Escolha entre `dateutil.relativedelta` (mais preciso pra fronteira de meses) ou `timedelta(days=180)` (evita adicionar dependência) fica pra o plan. Sem UI pra escolher outra janela — decisão travada no brainstorm (Q5).

## 9. Edge cases & degradação graciosa

Cada cenário abaixo tem tratamento explícito. Objetivo: nunca gerar PDF quebrado nem crashar o dashboard.

| Cenário | Comportamento |
|---------|---------------|
| Conta ML nova com < 3 meses de vendas | `cohort.build_ctx()` e `rfm.build_ctx()` detectam base insuficiente e retornam `resultado={"insuficiente": True, "motivo": "..."}`. Os partials respectivos renderizam um bloco de "Dados insuficientes — retenção precisa de pelo menos 3 meses". Demais seções renderizam normal. |
| Base RFM com < 10 compradores | `rfm.build_ctx()` renderiza a distribuição real, mas inclui `resultado={"disclaimer": "Base pequena (X compradores) — segmentação ganha valor a partir de 30+", ...}`. Partial mostra o disclaimer no bloco "Seu resultado". |
| Zero vendas em todo o período de 6 meses | Botão nem aparece no sidebar (condição `_base_tem_vendas_suficientes()` retorna `False`). Dashboard mostra `st.info` explicando. |
| Ingestão ainda rodando | Botão não aparece (`st.session_state.get("ingest_done") != True`). Fase 3 já cuida disso. |
| WeasyPrint falha (ex: GTK ausente, fonte não carrega) | `render_pdf` propaga exception. Handler no dashboard captura, mostra `st.error("Falha ao gerar PDF: {msg}")`. Log completo no console. Sessão fica intacta. Try again no próximo click. |
| Threshold de faixa exatamente na fronteira | Semântica: `FAIXAS[faixa]["max"]` é exclusivo. Ex: `verde.max = 2.0` significa `valor < 2.0`. Valor exatamente 2.0 cai em amarelo. Documentado no docstring de `classificar_faixa()` e testado nos bordos. |
| Cohort com 3-5 meses de dados (borderline) | Renderiza normal com os buckets disponíveis. Nada especial — o gráfico simplesmente tem menos colunas. Só o caso < 3 meses vira "insuficiente". |
| Vendedor com 1 categoria só (ABC degenera) | ABC classifica tudo como "A" trivialmente. `abc.build_ctx()` detecta (≤ 1 categoria distinta) e retorna `resultado={"trivial": True, "motivo": "Portfólio com uma única categoria — curva ABC precisa de pelo menos 2"}`. Partial mostra o motivo em vez do gráfico. |

## 10. Testes

### Estrutura

```
tests/
├── test_pdf_renderer/          # existe — expande com novo golden do template completo
│   ├── test_render_html_matches_golden.html   # regenerated
│   └── test_render_pdf_smoke.py               # inalterado
└── test_pdf_sections/          # NOVO
    ├── test_financeiro.py
    ├── test_produtos.py
    ├── test_reputacao.py
    ├── test_rfm.py
    ├── test_abc.py
    ├── test_cohort.py
    ├── test_common.py          # helpers + classificar_faixa
    └── goldens/
        ├── _financeiro.html
        ├── _produtos.html
        ├── _reputacao.html
        ├── _rfm.html
        ├── _abc.html
        └── _cohort.html
```

### O que cada `test_<secao>.py` cobre

- **Shape do `build_ctx()`** — todos os campos comuns (`explicacao`, `faixa`, `acoes`, `resultado`) presentes com tipos corretos.
- **Classificação de faixa nas bordas** — verde↔amarelo, amarelo↔vermelho. Uma fixture per borda.
- **Textos de ação** — assert que a lista `acoes` no dict devolvido bate exatamente com `FAIXAS[faixa]["acoes"]` (não há mutação inadvertida).
- **Degradação graciosa** — cenários de edge case da Seção 9 aplicáveis à seção (`insuficiente`, `trivial`, `disclaimer`).
- **Golden HTML do partial** — renderiza o partial isolado com fixture determinística, compara byte a byte com `goldens/_<secao>.html`. Diff se mudar HTML.

### `test_common.py`

- `classificar_faixa()` — ordering, exclusividade do max, `ValueError` em faixas mal-formadas.
- Helpers de formatação movidos de `pdf_renderer.py` mantêm os testes que já existem em `test_pdf_renderer/`.

### Coverage target

- `src/pdf_sections/*.py` — **≥ 90%** cada. Uncovered permitido só em except branches defensivas.
- `src/pdf_renderer.py` (novo, enxuto) — **100%** (só orquestração, fácil de cobrir).
- Dashboard: geração de PDF pelo botão não é testável via pytest (UI Streamlit) — aceita cobrir só via smoke manual no deploy (Task de release).

## 11. Compatibilidade com CLI atual

`python -m src.main gerar-pdf` continua funcionando **com o mesmo comando e a mesma UX de terminal**:

- Lê `data/demo.db`.
- Janela default resolvida via `_resolve_gerar_pdf_window()` existente (7 dias terminando 1 dia após MAX(date_closed)). **Não muda pra 6 meses** — o CLI mantém a janela curta pra fins de demo/teste rápido.
- Grava em `RELATORIOS/relatorio-{yyyy}-W{WW}.pdf` por default, ou no `--output` se passado.

O que **muda** é o conteúdo do PDF gerado: passa a usar o novo template de 6 seções em vez do template atual de 3 páginas. Isso é intencional — não faz sentido manter dois templates em paralelo. Comando, argumentos, filename e path de saída ficam idênticos.

Assinatura dual do novo `render_pdf` é o que permite isso: CLI passa `db_path=` e `output_path=`, dashboard passa `conn=`. `render_pdf` valida que exatamente um dos dois foi passado (raise `TypeError` senão).

**Consequência da mudança de escopo pro CLI:** o PDF gerado pelo `gerar-pdf` vira o **mesmo template novo** (6 seções, formato guia), mas com janela de 7 dias. Como Cohort/RFM precisam de meses, essas seções vão cair em "dados insuficientes" quase sempre no CLI rodando contra `demo.db`. Aceitável — o CLI vira showoff visual + demo do template, não análise real. Se quiser demo mais rica do CLI, o `demo_data.py` pode ser regenerado com 6 meses de dados sintéticos (fora de escopo desta fase; ticket separado).

## 12. Ordem de implementação recomendada

Pré-requisito absoluto: **Fase 2.5 (restyle navy/gold) merged em `main`**. Sem isso, quebrar o template em partials significa perder o trabalho de estilização paralelo.

Fases seguindo o pattern subagent-driven da Fase 3:

1. **Bootstrap** — cria pacote `pdf_sections/`, extrai `_common.py`, quebra `relatorio.html.j2` estilizado em `_layout.html.j2` + partials vazios (só com placeholders que geram o mesmo HTML atual). Golden idêntico ao pré-refactor. Bump `0.5.0-dev`.
2. **`_common.py` + `classificar_faixa()`** — helpers + testes.
3. **Seção 1: Financeiro** — módulo + partial + testes + golden.
4. **Seção 2: Reputação** — idem.
5. **Seção 3: Produtos** — idem (mais simples, sem faixa).
6. **Seção 4: ABC** — idem.
7. **Seção 5: RFM** — idem.
8. **Seção 6: Cohort** — idem.
9. **`render_pdf` assinatura dual** — refactor + testes cobrindo os 2 modos (conn vs db_path).
10. **Botão dashboard + edge cases** — sidebar, spinner, download_button, condições de aparição.
11. **Deploy staging + checklist manual** — smoke no `sellerpulse.streamlit.app`, gerar PDF real de conta ML de teste, revisar visual em pt-BR, checar filename.
12. **Release v0.5.0** — tag + notas.

Cada seção (Tasks 3-8) segue o loop implementer → spec reviewer → code quality reviewer, com modelo Opus (padrão da Fase 3). Estimativa: 12 tasks, ~2-3 dias de trabalho de sessão focada.

## 13. Critérios de sucesso mensuráveis

- CLI: `python -m src.main gerar-pdf` gera um PDF válido em `RELATORIOS/` a partir de `data/demo.db` (mesmo comportamento do golden atual). **Golden HTML raiz atualizado** e commitado.
- Dashboard: em sessão Real com conta conectada + 6 meses ingeridos, o botão "Baixar guia analytics (PDF)" aparece no sidebar e gera um PDF de 6 seções em ≤ 20s. Filename bate o padrão `guia-analytics-{seller_id}-{yyyymmdd}.pdf`.
- Todas as 5 seções com faixa (financeiro, reputação, ABC, RFM, cohort) mostram textos condicionais coerentes com o número real do vendedor. Nenhum texto sugere preço/produto/campanha específica (revisão manual antes do release).
- Suite `pytest` passa com ≥ 90% coverage em `src/pdf_sections/*` e 100% em `src/pdf_renderer.py`.
- Nenhuma modificação em `src/metrics.py` ou `src/segmentation.py`.
- `main.py` intacto exceto por assinatura de `render_pdf` (import) — resto do CLI (`_cmd_gerar_pdf`, argparse) sem mudanças de comportamento observável.
- Deploy no `sellerpulse.streamlit.app` funcional. Um smoke manual do fluxo completo (conectar → ingerir → gerar PDF → baixar) documentado.

## 14. Fora de escopo desta fase (backlog reconhecido)

- Redesenho visual profundo do PDF (visual atual navy/gold da Fase 2.5 é mantido).
- Fontes offline pré-embutidas no template (mitigar dependência de Google Fonts).
- Regeneração determinística do `demo.db` com 6 meses de dados sintéticos pra CLI gerar guia rico.
- Configuração de thresholds via YAML/JSON externo (hoje constantes em Python; se surgir demanda, ticket separado).
- Painel de "auditar textos condicionais" no dashboard (Guilherme abre e vê todos os 60 bullets pra verificar tom antes de gerar PDF pra um cliente).
- Export do PDF em outros formatos (DOCX, HTML standalone).
- Comparativo temporal ("guia de agosto vs. guia de julho").
- Métricas de forecasting/anomaly detection (planejadas na spec `2026-08-07-camadas-analiticas-design.md`) — aguardam módulo `forecasting.py` que ainda não existe.
