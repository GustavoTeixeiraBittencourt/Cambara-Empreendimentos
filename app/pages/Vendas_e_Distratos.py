import re
import sqlite3
from datetime import date

import streamlit as st

from core.db import run_query
from core.exceptions import (
    ClienteInvalidoError,
    UnidadeIndisponivelError,
    UnidadeNaoEncontradaError,
    VendaJaDistratadaError,
    VendaNaoEncontradaError,
)
from core.regras_negocio import (
    esta_ativa,
    registrar_distrato,
    registrar_venda,
    unidades_disponiveis,
)
from format_br import formatar_moeda_br

st.set_page_config(page_title="Vendas e Distratos — Cambará", page_icon="✍️", layout="wide")

if "usuario" not in st.session_state:
    st.warning("Faça login na página inicial para acessar esta página.")
    st.stop()

UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
]
PERFIS = ["Morador", "Investidor", "Institucional"]
FORMAS_PAGAMENTO = ["À vista", "Financiamento", "Parcelado Direto"]


def rotulo_unidade(u: dict) -> str:
    identificador = u.get("identificador") or f"Unidade {u.get('id')}"
    partes = [str(identificador)]
    nome_empreendimento = u.get("empreendimento_nome") or u.get("empreendimento")
    if nome_empreendimento:
        partes.append(str(nome_empreendimento))
    if u.get("tipo"):
        partes.append(str(u["tipo"]))
    if u.get("valor_tabela") is not None:
        partes.append(formatar_moeda_br(u["valor_tabela"]))
    return " — ".join(partes)


def rotulo_cliente(c: dict) -> str:
    return f"{c['nome']} — {c.get('cidade', '')}/{c.get('uf', '')}"


st.html(
    """<div class="exec-header">
        <div class="exec-eyebrow">Operações comerciais</div>
        <h1>Vendas e distratos</h1>
        <p>Registre novas vendas e formalize distratos diretamente sobre a base de dados.</p>
    </div>"""
)

aba_venda, aba_distrato = st.tabs([":material/sell: Registrar venda", ":material/assignment_return: Registrar distrato"])

# ---------------------------------------------------------------------------
# Registrar venda
# ---------------------------------------------------------------------------

with aba_venda:
    try:
        unidades = unidades_disponiveis()
    except Exception as e:
        unidades = []
        st.error("Não foi possível carregar as unidades disponíveis agora. Tente novamente em instantes.")
        with st.expander("Detalhes técnicos"):
            st.caption(str(e))

    if not unidades:
        st.info("Não há unidades disponíveis para venda no momento.")
    else:
        st.caption(f"{len(unidades)} unidade(s) disponível(is) para venda.")

        opcoes_unidade = {rotulo_unidade(u): u for u in unidades}
        rotulo_escolhido = st.selectbox("Unidade", list(opcoes_unidade.keys()), key="venda_unidade")
        unidade_selecionada = opcoes_unidade[rotulo_escolhido]

        tipo_cliente = st.radio("Cliente", ["Cliente já cadastrado", "Novo cliente"], key="venda_tipo_cliente")

        cliente_id = None
        cliente_novo = None

        if tipo_cliente == "Cliente já cadastrado":
            try:
                clientes = run_query("SELECT id, nome, cidade, uf FROM clientes ORDER BY nome")
            except Exception as e:
                clientes = []
                st.error("Não foi possível carregar a lista de clientes agora. Tente novamente em instantes.")
                with st.expander("Detalhes técnicos"):
                    st.caption(str(e))

            if clientes:
                opcoes_cliente = {rotulo_cliente(c): c["id"] for c in clientes}
                rotulo_cliente_escolhido = st.selectbox(
                    "Selecione o cliente", list(opcoes_cliente.keys()), key="venda_cliente_existente"
                )
                cliente_id = opcoes_cliente[rotulo_cliente_escolhido]
        else:
            col1, col2 = st.columns(2)
            with col1:
                nome_novo = st.text_input("Nome do cliente", key="venda_novo_nome")
                cidade_novo = st.text_input("Cidade", key="venda_novo_cidade")
                email_novo = st.text_input("E-mail", key="venda_novo_email")
            with col2:
                uf_novo = st.selectbox("UF", UFS, key="venda_novo_uf")
                perfil_novo = st.selectbox("Perfil", PERFIS, key="venda_novo_perfil")

        st.markdown("**Dados da venda**")
        col1, col2, col3 = st.columns(3)
        with col1:
            data_venda = st.date_input("Data da venda", value=date.today(), key="venda_data")
        with col2:
            valor_padrao = float(unidade_selecionada.get("valor_tabela") or 0) or 0.01
            valor_venda = st.number_input(
                "Valor da venda (R$)", min_value=0.01, value=valor_padrao, step=1000.0, key="venda_valor"
            )
            st.caption(formatar_moeda_br(valor_venda))
        with col3:
            forma_pagamento = st.selectbox("Forma de pagamento", FORMAS_PAGAMENTO, key="venda_forma_pagamento")

        if st.button("Registrar venda", type="primary", key="venda_submit"):
            if tipo_cliente == "Novo cliente":
                if not nome_novo or not cidade_novo:
                    st.error("Preencha nome e cidade do novo cliente.")
                    st.stop()
                if email_novo and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email_novo):
                    st.error("Informe um e-mail válido para o novo cliente, ou deixe o campo em branco.")
                    st.stop()
                cliente_novo = {
                    "nome": nome_novo,
                    "cidade": cidade_novo,
                    "uf": uf_novo,
                    "perfil": perfil_novo,
                    "email": email_novo,
                }
            elif cliente_id is None:
                st.error("Selecione um cliente existente.")
                st.stop()

            if valor_venda <= 0:
                st.error("Informe um valor de venda maior que zero.")
                st.stop()

            try:
                resultado = registrar_venda(
                    unidade_id=unidade_selecionada["id"],
                    cliente_id=cliente_id,
                    cliente_novo=cliente_novo,
                    data_venda=str(data_venda),
                    valor_venda=valor_venda,
                    forma_pagamento=forma_pagamento,
                )
            except (UnidadeIndisponivelError, UnidadeNaoEncontradaError):
                st.error(
                    "Esta unidade não está mais disponível para venda — provavelmente foi vendida "
                    "ou reservada por outra transação. Atualize a lista e escolha outra unidade."
                )
            except ClienteInvalidoError:
                st.error(
                    "O cliente selecionado não foi encontrado na base. Atualize a lista de clientes "
                    "e tente novamente, ou cadastre um novo cliente."
                )
            except ValueError as e:
                st.error(f"Dados da venda inválidos: {e}")
            except sqlite3.OperationalError:
                st.error(
                    "Outra operação pode estar em andamento sobre esta unidade agora. "
                    "Aguarde alguns instantes e tente novamente."
                )
            except Exception as e:
                st.error("Não foi possível registrar a venda agora. Tente novamente em instantes.")
                with st.expander("Detalhes técnicos"):
                    st.caption(str(e))
            else:
                st.success(
                    f"Venda registrada com sucesso! (venda #{resultado['venda_id']}, "
                    f"unidade #{resultado['unidade_id']}, cliente #{resultado['cliente_id']})"
                )
                st.rerun()

# ---------------------------------------------------------------------------
# Registrar distrato
# ---------------------------------------------------------------------------

with aba_distrato:
    try:
        vendas_raw = run_query(
            """
            SELECT v.id, v.data_venda, v.valor_venda, v.status_venda, v.data_distrato,
                   c.nome AS cliente_nome, u.identificador AS unidade_identificador
            FROM vendas v
            JOIN clientes c ON c.id = v.cliente_id
            JOIN unidades u ON u.id = v.unidade_id
            ORDER BY v.data_venda DESC
            """
        )
    except Exception as e:
        vendas_raw = []
        st.error("Não foi possível carregar as vendas agora. Tente novamente em instantes.")
        with st.expander("Detalhes técnicos"):
            st.caption(str(e))

    vendas_ativas = [v for v in vendas_raw if esta_ativa(v["status_venda"], v["data_distrato"])]

    if not vendas_ativas:
        st.info("Não há vendas ativas para distratar no momento.")
    else:
        st.caption(f"{len(vendas_ativas)} venda(s) ativa(s).")

        def rotulo_venda(v: dict) -> str:
            return (
                f"Venda #{v['id']} — {v['cliente_nome']} — unidade {v['unidade_identificador']} — "
                f"{formatar_moeda_br(v['valor_venda'])} — vendida em {v['data_venda']}"
            )

        opcoes_venda = {rotulo_venda(v): v["id"] for v in vendas_ativas}
        rotulo_venda_escolhida = st.selectbox("Venda", list(opcoes_venda.keys()), key="distrato_venda")
        venda_id_selecionada = opcoes_venda[rotulo_venda_escolhida]

        data_distrato = st.date_input("Data do distrato", value=date.today(), key="distrato_data")

        if st.button("Registrar distrato", type="primary", key="distrato_submit"):
            try:
                resultado = registrar_distrato(venda_id_selecionada, str(data_distrato))
            except VendaNaoEncontradaError:
                st.error("Esta venda não foi encontrada na base — ela pode ter sido removida.")
            except VendaJaDistratadaError:
                st.error("Esta venda já está distratada. Não é possível registrar o distrato novamente.")
            except sqlite3.OperationalError:
                st.error(
                    "Outra operação pode estar em andamento sobre esta venda agora. "
                    "Aguarde alguns instantes e tente novamente."
                )
            except Exception as e:
                st.error("Não foi possível registrar o distrato agora. Tente novamente em instantes.")
                with st.expander("Detalhes técnicos"):
                    st.caption(str(e))
            else:
                st.success(
                    f"Distrato registrado com sucesso! A unidade #{resultado['unidade_id']} passou para o "
                    f"status \"{resultado['novo_status_unidade']}\" e precisa de liberação manual para "
                    "voltar a ficar disponível para venda."
                )
                st.rerun()
