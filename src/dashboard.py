"""SellerPulse dashboard — entry point Streamlit.

Rodar via `python -m src.main abrir-dashboard` (usa `streamlit run` internamente).
Multi-page é gerenciado nativamente pelo Streamlit lendo a pasta `src/pages/`.
A sidebar aqui é global — grava período em `st.session_state` para as páginas.
"""

from __future__ import annotations

import secrets as py_secrets
from datetime import UTC, date, datetime, timedelta
from importlib import metadata

import streamlit as st
from dotenv import load_dotenv

from src import theme
from src.dashboard_helpers import (
    clear_ml_session_state,
    get_active_ml_client,
    get_config,
    is_ml_connected,
)
from src.ingest import ingest_last_6_months
from src.session_auth import (
    OAuthError,
    build_authorize_url,
    exchange_code_for_tokens,
    sanitize_oauth_error,
)
from src.session_store import InMemoryTokenStore, create_session_db

load_dotenv()

st.set_page_config(page_title="SellerPulse", page_icon="📊", layout="wide")


def _get_version() -> str:
    try:
        return metadata.version("sellerpulse")
    except metadata.PackageNotFoundError:
        return "dev"


def _handle_oauth_callback() -> None:
    """Se st.query_params tem `code` + `state`, processa exchange + ingest.

    Roda ANTES da sidebar em todo run. Se não há code, é no-op.
    Se há erro no callback (usuário cancelou, state inválido, exchange falha),
    seta session_state["oauth_error_message"] pra sidebar mostrar.
    """
    params = st.query_params
    if "error" in params:
        st.session_state["oauth_error_message"] = (
            "Autorização cancelada. Você pode tentar de novo quando quiser."
        )
        st.session_state.pop("oauth_state", None)
        st.query_params.clear()
        return

    code = params.get("code")
    state_received = params.get("state")
    if not code or not state_received:
        if code or state_received:
            # Um veio sem o outro — payload anômalo, limpa pra não reprocessar em reruns.
            st.query_params.clear()
        return

    # Valida ANTES de consumir state/params — falhar aqui não desperdiça o CSRF
    # token nem o auth code em um rerun antes de decidir o que fazer.
    state_expected = st.session_state.get("oauth_state")
    if not state_expected or not py_secrets.compare_digest(state_expected, state_received):
        st.session_state["oauth_error_message"] = (
            "Falha de segurança na autenticação, tente novamente."
        )
        st.session_state.pop("oauth_state", None)
        st.query_params.clear()
        return

    # Match confirmado — state e code são single-use, consome agora.
    st.session_state.pop("oauth_state", None)
    st.query_params.clear()

    client_id = get_config("ML_CLIENT_ID")
    client_secret = get_config("ML_CLIENT_SECRET")
    redirect_uri = get_config("ML_REDIRECT_URI")
    if not (client_id and client_secret and redirect_uri):
        st.session_state["oauth_error_message"] = (
            "SellerPulse não está configurado corretamente (secrets faltando). Contate o admin."
        )
        return

    try:
        tokens = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
    except OAuthError as exc:
        st.session_state["oauth_error_message"] = sanitize_oauth_error(str(exc))
        return

    store = InMemoryTokenStore()
    store.save(tokens)
    st.session_state["ml_tokens"] = tokens
    st.session_state["ml_token_store"] = store
    st.session_state["_trigger_post_oauth_ingest"] = True


@st.dialog("Conectar sua conta Mercado Livre")
def _consent_dialog() -> None:
    client_id = get_config("ML_CLIENT_ID")
    redirect_uri = get_config("ML_REDIRECT_URI")
    if not (client_id and redirect_uri):
        st.error("SellerPulse não está configurado corretamente. Contate o admin.")
        return

    # State anti-CSRF é gerado uma vez por diálogo aberto — reruns do Streamlit
    # não devem trocar o URL renderizado no botão (o callback valida contra o
    # mesmo state persistido aqui). Cancelar limpa; nova abertura gera novo.
    if "oauth_state" not in st.session_state:
        st.session_state["oauth_state"] = py_secrets.token_urlsafe(32)
    authorize_url = build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=st.session_state["oauth_state"],
    )

    st.markdown(
        "Vamos te redirecionar pro Mercado Livre pra você autorizar o acesso.\n\n"
        "O SellerPulse vai poder:\n"
        "- ✓ Ler seus pedidos dos últimos 6 meses\n"
        "- ✓ Ler dados de produtos vendidos\n"
        "- ✓ Ler reclamações da conta\n\n"
        "**Não podemos** alterar preços, criar anúncios ou responder mensagens.\n\n"
        "Seus dados ficam apenas nesta sessão do navegador. Quando fechar a aba, "
        "tudo é apagado."
    )
    col_a, col_b = st.columns(2)
    if col_a.button("Cancelar", key="btn_cancel_consent", use_container_width=True):
        st.session_state.pop("oauth_state", None)
        st.rerun()
    with col_b:
        st.link_button(
            "Continuar no ML →",
            url=authorize_url,
            use_container_width=True,
            type="primary",
        )


def _run_ingest_with_progress() -> None:
    """Executa ingest_last_6_months mostrando progresso via st.status."""
    client = get_active_ml_client()
    if client is None:
        st.error("Erro interno: token não disponível para ingestão.")
        return

    with st.status("Baixando seus dados...", expanded=True) as status:
        try:
            st.write("Identificando conta...")
            me = client.get("/users/me")
            seller_id = int(me["id"])
            nickname = me.get("nickname", f"conta {seller_id}")
            st.session_state["ml_seller_id"] = seller_id
            st.session_state["ml_nickname"] = nickname
            store = st.session_state["ml_token_store"]
            store.set_seller_id(seller_id)

            session_conn = create_session_db()
            st.session_state["session_conn"] = session_conn

            def _on_progress(fase: str, atual: int, total: int) -> None:
                if total > 0:
                    status.update(label=f"⟳ {fase}... ({atual}/{total})")
                else:
                    status.update(label=f"⟳ {fase}...")

            result = ingest_last_6_months(
                client=client,
                seller_id=seller_id,
                conn=session_conn,
                on_progress=_on_progress,
            )

            st.session_state["ingest_result"] = result
            st.session_state["ingest_done_at"] = datetime.now(UTC).isoformat()
            st.cache_data.clear()
            status.update(
                label=f"✓ Dados carregados! {result.total_orders} pedidos processados.",
                state="complete",
            )
        except Exception as exc:  # noqa: BLE001 — boundary
            # Qualquer falha (identificação, set_seller_id, create_session_db, ingest)
            # vira status=error no widget — evita stack trace vazando pro usuário.
            status.update(
                label=f"Falha na ingestão: {sanitize_oauth_error(str(exc))}",
                state="error",
            )
            return
    st.rerun()


def _render_sidebar() -> None:
    st.sidebar.markdown(
        '<div class="sp-brand">'
        '<div class="sp-brand__name">Seller<em>Pulse</em></div>'
        f'<div class="sp-brand__version">v{_get_version()}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    with st.sidebar.container(border=True):
        st.markdown(
            '<div class="sp-card__head"><span class="sp-card__title">Período</span></div>',
            unsafe_allow_html=True,
        )
        date_from = st.date_input("Início", value=default_from, key="sidebar_date_from")
        date_to = st.date_input("Fim", value=default_to, key="sidebar_date_to")
    st.session_state["date_from"] = date_from.isoformat()
    st.session_state["date_to"] = date_to.isoformat()

    with st.sidebar.container(border=True):
        st.markdown(
            '<div class="sp-card__head"><span class="sp-card__title">Fonte de dados</span></div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "Modo",
            options=["Demo", "Real"],
            index=0,
            captions=["Dados sintéticos versionados", "Sua conta Mercado Livre"],
            key="sidebar_modo",
        )
        st.selectbox(
            "Categoria",
            options=["Todas"],
            index=0,
            disabled=True,
            help="Disponível na v1.0",
            key="sidebar_categoria",
        )

    modo = st.session_state.get("sidebar_modo", "Demo")
    if modo == "Real":
        _render_real_mode_sidebar()


def _render_real_mode_sidebar() -> None:
    """Sidebar sub-section pro modo Real — estados 2 e 5."""
    connected = is_ml_connected()

    if not connected:
        # Estado 2: Real, sem conta conectada
        st.sidebar.warning("⚠ Nenhuma conta conectada. Ainda vendo dados demo.")
        if st.sidebar.button("🔌 Conectar minha conta", key="btn_connect"):
            st.session_state["_trigger_oauth"] = True
            st.rerun()
        return

    # Estado 5: Real, conectado
    nickname = st.session_state.get("ml_nickname", "sua conta")
    st.sidebar.success(f"🟢 Conectado: {nickname}")
    result = st.session_state.get("ingest_result")
    done_at = st.session_state.get("ingest_done_at", "")
    if result is not None:
        st.sidebar.caption(f"{result.total_orders} pedidos · 6 meses\n\nAtualizado: {done_at[:16]}")
    col_a, col_b = st.sidebar.columns(2)
    if col_a.button("🔄 Recarregar", key="btn_reingest"):
        st.session_state["_trigger_reingest"] = True
        st.rerun()
    if col_b.button("⛔ Desconectar", key="btn_disconnect"):
        st.session_state["_trigger_disconnect"] = True
        st.rerun()


def _handle_triggers() -> None:
    """Executa ações triggadas por botões da sidebar ou fluxo OAuth."""
    if err := st.session_state.pop("oauth_error_message", None):
        st.error(err)

    if st.session_state.pop("_trigger_oauth", False):
        _consent_dialog()

    if st.session_state.pop("_trigger_post_oauth_ingest", False):
        _run_ingest_with_progress()

    if st.session_state.pop("_trigger_reingest", False):
        st.session_state.pop("session_conn", None)
        st.session_state.pop("ingest_result", None)
        _run_ingest_with_progress()

    if st.session_state.pop("_trigger_disconnect", False):
        clear_ml_session_state()
        st.cache_data.clear()
        st.toast("Desconectado. Seus dados foram removidos da sessão.")
        st.rerun()


def _render_home() -> None:
    periodo = f"{st.session_state['date_from']} — {st.session_state['date_to']}"
    st.markdown(
        '<div class="sp-cover">'
        '<div class="sp-cover__name">Seller<em>Pulse</em></div>'
        '<p class="sp-cover__tagline">Analytics para vendedores Mercado Livre.</p>'
        f'<span class="sp-pill">{periodo}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        theme.nav_card(
            "Executive",
            "Receita, custos e resultado do período, com variação sobre a janela anterior.",
            "revenue",
            "pages/1_executive.py",
        )
    with col2:
        theme.nav_card(
            "Products",
            "Top produtos e categorias, curva Pareto ABC e cohort por mês de lançamento.",
            "box",
            "pages/2_products.py",
        )
    with col3:
        theme.nav_card(
            "Customers",
            "Segmentação RFM dos compradores e distribuição por segmento.",
            "users",
            "pages/3_customers.py",
        )


theme.inject_css()
_handle_oauth_callback()
_handle_triggers()
_render_sidebar()
_render_home()
