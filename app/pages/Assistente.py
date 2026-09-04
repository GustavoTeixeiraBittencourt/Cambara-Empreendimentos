import os

import pandas as pd
import streamlit as st

from core.db import caminho_banco
from format_br import column_config_centralizado, formatar_dataframe_heuristico
from nl_assistant.text_to_sql import perguntar

st.set_page_config(page_title="Assistente — Cambará", page_icon="🤖", layout="wide")

if "usuario" not in st.session_state:
    st.warning("Faça login na página inicial para acessar o assistente.")
    st.stop()

st.html(
    """<div class="exec-header">
        <div class="exec-eyebrow">Consulta em linguagem natural</div>
        <h1>Assistente de perguntas</h1>
        <p>Pergunte em português sobre os dados de vendas, unidades, clientes, obras ou financeiro.
        O assistente consulta o banco de dados real. O resultado da consulta aparece junto com a
        resposta; a consulta SQL usada e o banco de dados consultado ficam num log de auditoria
        expansível, para rastreabilidade sem poluir a resposta principal.</p>
    </div>"""
)

if "historico_assistente" not in st.session_state:
    st.session_state["historico_assistente"] = []

col_pergunta, col_limpar = st.columns([5, 1], vertical_alignment="bottom")
with col_pergunta:
    pergunta = st.text_area(
        "Sua pergunta",
        placeholder="Ex.: Quais os 5 empreendimentos com maior valor total de vendas ativas?",
        key="assistente_pergunta",
    )
with col_limpar:
    if st.session_state["historico_assistente"] and st.button(
        "🗑️ Limpar histórico", width="stretch"
    ):
        st.session_state["historico_assistente"] = []
        st.rerun()

if st.button("Perguntar", type="primary") and pergunta.strip():
    with st.spinner("Consultando os dados..."):
        try:
            resposta = perguntar(pergunta)
        except ValueError as e:
            st.error("Essa pergunta gerou uma consulta que não pôde ser executada com segurança. Tente reformular.")
            with st.expander("Detalhes técnicos"):
                st.caption(str(e))
        except Exception as e:
            st.error("Não foi possível responder agora. Tente novamente em instantes.")
            with st.expander("Detalhes técnicos"):
                st.caption(str(e))
        else:
            st.session_state["historico_assistente"].insert(0, {"pergunta": pergunta, **resposta})

if not st.session_state["historico_assistente"]:
    st.info("Faça sua primeira pergunta acima.")
else:
    nome_banco = os.path.basename(caminho_banco())
    for item in st.session_state["historico_assistente"]:
        st.markdown(f"**Pergunta:** {item['pergunta']}")
        st.markdown(f"**Resposta:** {item['resposta_texto']}")

        if item["resultado"]:
            df_resultado = formatar_dataframe_heuristico(pd.DataFrame(item["resultado"]))
            st.dataframe(
                df_resultado,
                column_config=column_config_centralizado(df_resultado),
                hide_index=True,
            )
        elif item["sql"]:
            st.caption("A consulta não retornou nenhuma linha.")

        with st.expander("🧾 Log de auditoria (SQL e fonte)"):
            st.caption(f"Banco de dados consultado: `{nome_banco}`")
            st.caption("SQL executada")
            if item["sql"]:
                st.code(item["sql"], language="sql")
            else:
                st.write("Nenhuma consulta foi executada para esta resposta.")

        st.divider()
