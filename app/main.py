import os

from dotenv import load_dotenv

# override=True: por padrão, load_dotenv() nunca sobrescreve uma variável já
# presente em os.environ — inclusive uma que ela mesma setou como vazia numa
# execução anterior deste mesmo processo (ex.: GROQ_API_KEY vazia no .env
# quando o Streamlit subiu, preenchida depois sem reiniciar o servidor).
# Sem override=True, esse valor vazio fica travado pelo resto da vida do
# processo, e nenhum rerun corrige sozinho. Como o .env deste projeto só
# define GROQ_API_KEY (nada usado por variável de ambiente "real" do SO),
# forçar o arquivo a sempre vencer é seguro aqui.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

import streamlit as st

from components.assistant_widget import render_assistant
from core.auth import autenticar

st.set_page_config(page_title="Cambará Empreendimentos S.A.", page_icon="🏗️", layout="wide")

EXEC_CSS = """
<style>
:root {
    --exec-bg: #F6F0E4;
    --exec-card: #FFFDF8;
    --exec-brown: #70451F;
    --exec-brown-soft: #8B623B;
    --exec-brown-light: #B89A72;
    --exec-text: #2C241D;
    --exec-text-soft: #766B5E;
    --exec-border: #DCCBB2;
    --exec-hover: #E7D5B8;
    --exec-active: #DCC7A5;
}

[data-testid="stMainBlockContainer"] { padding-top: 4.5rem; }

/* ---- Sidebar ---- */
[data-testid="stSidebar"] { border-right: 1px solid var(--exec-border); }
[data-testid="stSidebarContent"] { padding-top: 0.5rem; }
[data-testid="stSidebarNavItems"] { row-gap: 0.2rem; padding-top: 0.5rem; }
[data-testid="stSidebarNavLink"] {
    border-radius: 8px;
    padding-top: 0.6rem;
    padding-bottom: 0.6rem;
    transition: background-color 120ms ease;
}
[data-testid="stSidebarNavLink"]:hover { background-color: var(--exec-hover) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] { background-color: var(--exec-active) !important; }
[data-testid="stSidebarNavLink"][aria-current="page"] span { color: var(--exec-brown) !important; }

/* ---- Header block (used across pages) ---- */
.exec-header { margin: 0.25rem 0 1.75rem 0; }
.exec-header.exec-header-center { text-align: center; }
.exec-header.exec-header-center p { margin-left: auto; margin-right: auto; }
.exec-header .exec-eyebrow {
    font-size: 12px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--exec-brown-soft);
    font-weight: 600;
    margin-bottom: 0.4rem;
}
.exec-header h1 {
    font-size: 36px;
    line-height: 1.15;
    font-weight: 700;
    color: var(--exec-text);
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.01em;
}
.exec-header p {
    font-size: 15px;
    color: var(--exec-text-soft);
    margin: 0;
    max-width: 640px;
}
.exec-header .exec-subtitle {
    font-size: 19px;
    font-weight: 600;
    color: var(--exec-brown-soft);
    margin: 0 0 0.75rem 0;
}

/* ---- KPI navigation (tabs) ---- */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 2rem;
    border-bottom: 1px solid var(--exec-border);
}
[data-testid="stTab"] { padding-left: 0.1rem !important; padding-right: 0.1rem !important; }
[data-testid="stTab"] p { color: var(--exec-text-soft); font-size: 14px; font-weight: 500; }
[data-testid="stTab"][aria-selected="true"] p { color: var(--exec-brown); font-weight: 600; }

/* ---- Cards (containers created with key="exec-card-...") ---- */
[class*="st-key-exec-card"] {
    background: var(--exec-card);
    box-shadow: 0 2px 8px rgba(80, 50, 20, 0.04);
}

/* ---- Metrics as KPI cards ---- */
[data-testid="stMetric"] {
    background: var(--exec-card);
    border-radius: 10px;
    box-shadow: 0 2px 8px rgba(80, 50, 20, 0.04);
    padding: 1rem 1.1rem !important;
}
[data-testid="stMetricLabel"] p {
    font-size: 11px !important;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--exec-text-soft) !important;
    font-weight: 600 !important;
}
[data-testid="stMetricValue"] { color: var(--exec-text) !important; font-weight: 700 !important; }

/* ---- Dataframes ---- */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ---- Insight blocks ---- */
.exec-insight {
    background: var(--exec-card);
    border: 1px solid var(--exec-border);
    border-left: 3px solid var(--exec-brown);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin: 0.75rem 0;
}
.exec-insight .exec-tag {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--exec-brown);
    margin-bottom: 0.3rem;
}
.exec-insight .exec-tag.exec-tag-muted { color: var(--exec-text-soft); }
.exec-insight p {
    font-size: 14px;
    color: var(--exec-text);
    margin: 0 0 0.75rem 0;
    line-height: 1.5;
}
.exec-insight p:last-child { margin-bottom: 0; }
</style>
"""

st.html(EXEC_CSS)


def pagina_login():
    st.html(
        """<div class="exec-header exec-header-center">
            <h1>Cambará Empreendimentos S.A.</h1>
            <div class="exec-subtitle">Acesso ao sistema</div>
            <p>Entre com suas credenciais para acessar o painel executivo de indicadores comerciais.</p>
        </div>"""
    )

    st.space("large")

    _, col_form, _ = st.columns([1, 1.1, 1])
    with col_form:
        with st.container(border=True, key="exec-card-login"):
            with st.form("form_login"):
                email = st.text_input("E-mail")
                senha = st.text_input("Senha", type="password")
                enviado = st.form_submit_button("Entrar", type="primary", width="stretch")

    if enviado:
        if not email or not senha:
            st.error("Preencha e-mail e senha para continuar.")
            return
        try:
            usuario = autenticar(email, senha)
        except Exception as e:
            st.error("Não foi possível acessar o sistema agora. Tente novamente em instantes.")
            with st.expander("Detalhes técnicos"):
                st.caption(str(e))
            return
        if usuario is None:
            st.error("E-mail ou senha incorretos.")
        else:
            st.session_state["usuario"] = usuario
            st.rerun()


pagina_login_obj = st.Page(pagina_login, title="Login", icon=":material/login:")
pagina_dashboard = st.Page("pages/Dashboard.py", title="Dashboard", icon=":material/bar_chart:")
pagina_qualidade = st.Page(
    "pages/Qualidade_de_Dados.py", title="Qualidade de Dados", icon=":material/verified:"
)
pagina_vendas = st.Page(
    "pages/Vendas_e_Distratos.py", title="Vendas e Distratos", icon=":material/edit_document:"
)
pagina_assistente = st.Page(
    "pages/Assistente.py", title="Assistente", icon=":material/smart_toy:"
)

if "usuario" in st.session_state:
    with st.sidebar:
        if st.button("Sair", icon=":material/logout:", width="stretch"):
            del st.session_state["usuario"]
            st.rerun()
    paginas = [pagina_dashboard, pagina_qualidade, pagina_vendas, pagina_assistente]
else:
    paginas = [pagina_login_obj]

navegacao = st.navigation(paginas)
navegacao.run()

if "usuario" in st.session_state:
    render_assistant(pagina_atual=navegacao.title)
