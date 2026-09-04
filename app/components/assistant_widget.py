import pandas as pd
import streamlit as st

from format_br import column_config_centralizado, formatar_dataframe_heuristico
from nl_assistant.copiloto import PERGUNTAS_SUGERIDAS, responder

_ASSISTANT_CSS = """
<style>
.st-key-assistant-launcher {
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 9999;
}
.st-key-assistant-launcher [data-testid="stPopoverButton"] {
    width: 60px;
    height: 60px;
    min-width: 60px;
    border-radius: 50%;
    background: #70451F;
    border: none;
    box-shadow: 0 4px 14px rgba(80, 50, 20, 0.18);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 !important;
    transition: transform 120ms ease, box-shadow 120ms ease;
}
.st-key-assistant-launcher [data-testid="stPopoverButton"]:hover {
    transform: scale(1.06);
    box-shadow: 0 6px 20px rgba(80, 50, 20, 0.24);
}
.st-key-assistant-launcher [data-testid="stPopoverButton"] svg { display: none; }
.st-key-assistant-launcher [data-testid="stPopoverButton"] div[aria-hidden="true"] {
    display: none;
}
.st-key-assistant-launcher [data-testid="stPopoverButton"] p {
    color: #FFFDF8 !important;
    font-size: 34px;
    margin: 0;
    line-height: 1;
}

[data-testid="stPopoverBody"] {
    width: 380px !important;
    max-width: calc(100vw - 32px);
    background: #FFFDF8;
    border: 1px solid #DCCBB2 !important;
    border-radius: 14px !important;
    box-shadow: 0 8px 28px rgba(80, 50, 20, 0.14) !important;
    z-index: 10000 !important;
}

.st-key-assistant-header-row {
    display: flex;
    align-items: baseline;
    padding-bottom: 0.6rem;
    margin-bottom: 0.6rem;
    border-bottom: 1px solid #DCCBB2;
}
.st-key-assistant-header-row [data-testid="stButton"] button {
    padding: 0.2rem 0.4rem;
    min-height: unset;
}
.exec-assistant-header {
    display: flex;
    align-items: baseline;
    gap: 0.45rem;
}
.exec-assistant-header .exec-assistant-title {
    font-size: 15px;
    font-weight: 700;
    color: #2C241D;
}
.exec-assistant-header .exec-assistant-subtitle {
    font-size: 12px;
    color: #766B5E;
}
</style>
"""


def render_assistant(pagina_atual: str | None = None) -> None:
    """
    Renderiza o assistente flutuante de análise de negócio (botão + chat em popover).

    Deve ser chamado uma única vez, globalmente, após a navegação (em app/main.py) —
    nunca dentro de páginas individuais, para não duplicar o componente.
    """
    st.html(_ASSISTANT_CSS)

    if "assistant_historico" not in st.session_state:
        st.session_state["assistant_historico"] = []
    historico: list[dict] = st.session_state["assistant_historico"]

    with st.popover("🤖", key="assistant-launcher"):
        with st.container(key="assistant-header-row"):
            col_titulo, col_limpar = st.columns([4, 1], vertical_alignment="center")
            with col_titulo:
                st.html(
                    """<div class="exec-assistant-header">
                        <span class="exec-assistant-title">🤖 Assistente</span>
                        <span class="exec-assistant-subtitle">Copiloto de análise</span>
                    </div>"""
                )
            with col_limpar:
                if historico and st.button(
                    "🗑️", key="assistant-limpar", help="Limpar conversa"
                ):
                    st.session_state["assistant_historico"] = []
                    st.rerun()

        area_mensagens = st.container(height=360)
        with area_mensagens:
            if not historico:
                st.caption(
                    "Olá! Posso ajudar a interpretar os indicadores deste dashboard. "
                    "Pergunte algo ou escolha uma sugestão abaixo."
                )
                for sugestao in PERGUNTAS_SUGERIDAS:
                    if st.button(sugestao, key=f"assistant-sugestao-{sugestao}", width="stretch"):
                        _processar_pergunta(sugestao, pagina_atual, historico)
            else:
                for item in historico:
                    with st.chat_message(item["role"]):
                        st.write(item["content"])
                        if item.get("sql"):
                            st.caption("SQL gerada")
                            st.code(item["sql"], language="sql")
                            if item.get("resultado"):
                                st.caption("Resultado bruto")
                                df_resultado = formatar_dataframe_heuristico(pd.DataFrame(item["resultado"]))
                                st.dataframe(
                                    df_resultado,
                                    column_config=column_config_centralizado(df_resultado),
                                    hide_index=True,
                                )
                            else:
                                st.caption("A consulta não retornou nenhuma linha.")

        pergunta = st.chat_input("Pergunte sobre os dados...", key="assistant-chat-input")
        if pergunta:
            _processar_pergunta(pergunta, pagina_atual, historico)


def _processar_pergunta(pergunta: str, pagina_atual: str | None, historico: list[dict]) -> None:
    historico_anterior = list(historico)
    historico.append({"role": "user", "content": pergunta})

    with st.spinner("Consultando os dados..."):
        try:
            resposta = responder(pergunta, pagina_atual=pagina_atual, historico=historico_anterior)
        except Exception:
            resposta = {
                "resposta_texto": "Não foi possível consultar o assistente neste momento.",
                "sql": None,
                "resultado": None,
            }

    historico.append(
        {
            "role": "assistant",
            "content": resposta["resposta_texto"],
            "sql": resposta.get("sql"),
            "resultado": resposta.get("resultado"),
        }
    )
    st.rerun()
