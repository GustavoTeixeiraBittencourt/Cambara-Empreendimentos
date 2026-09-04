import pandas as pd
import streamlit as st

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
        O assistente consulta o banco de dados real — a consulta gerada e o resultado bruto ficam
        sempre visíveis abaixo da resposta, para que ela seja rastreável até os dados.</p>
    </div>"""
)

if "historico_assistente" not in st.session_state:
    st.session_state["historico_assistente"] = []

pergunta = st.text_area(
    "Sua pergunta",
    placeholder="Ex.: Quais os 5 empreendimentos com maior valor total de vendas ativas?",
    key="assistente_pergunta",
)

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
    for item in st.session_state["historico_assistente"]:
        st.markdown(f"**Pergunta:** {item['pergunta']}")
        st.markdown(f"**Resposta:** {item['resposta_texto']}")

        st.caption("SQL gerada")
        st.code(item["sql"], language="sql")

        st.caption("Resultado bruto da consulta")
        if item["resultado"]:
            st.dataframe(pd.DataFrame(item["resultado"]), hide_index=True)
        else:
            st.write("A consulta não retornou nenhuma linha.")

        st.divider()
