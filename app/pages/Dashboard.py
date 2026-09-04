import altair as alt
import pandas as pd
import streamlit as st

from analytics.velocidade_vendas import calcular as calcular_velocidade_vendas
from analytics.estouro_custo import calcular as calcular_estouro_custo
from analytics.clientes_duplicados import calcular as calcular_clientes_duplicados
from analytics.divergencia_financeira import calcular as calcular_divergencia_financeira
from format_br import formatar_colunas_br, formatar_moeda_br, formatar_percentual_br

st.set_page_config(page_title="Dashboard — Cambará", page_icon="📊", layout="wide")

if "usuario" not in st.session_state:
    st.warning("Faça login na página inicial para acessar o dashboard.")
    st.stop()


def insight(texto_insight: str, texto_recomendacao: str) -> None:
    st.html(
        f"""<div class="exec-insight">
            <div class="exec-tag">Insight</div>
            <p>{texto_insight}</p>
            <div class="exec-tag exec-tag-muted">Recomendação</div>
            <p>{texto_recomendacao}</p>
        </div>"""
    )


st.html(
    f"""<div class="exec-header">
        <div class="exec-eyebrow">Bem-vindo(a), {st.session_state['usuario']['nome']}</div>
        <h1>Dashboard de negócio</h1>
        <p>Uma visão executiva dos principais indicadores comerciais.</p>
    </div>"""
)
st.caption(
    "As 4 perguntas de negócio, com o tratamento de dado que sustenta cada indicador. "
    "Veja como os dados foram verificados e corrigidos na página **Qualidade de Dados**, no menu ao lado."
)

aba1, aba2, aba3, aba4 = st.tabs(
    [
        ":material/trending_up: Velocidade de vendas",
        ":material/construction: Estouro de custo",
        ":material/group: Clientes duplicados",
        ":material/paid: Divergência financeira",
    ]
)

COLUNAS_VELOCIDADE = {
    "empreendimento": st.column_config.TextColumn("Empreendimento"),
    "total_ofertado": st.column_config.TextColumn("Unidades colocadas à venda"),
    "vendas_liquidas": st.column_config.TextColumn("Vendas que continuam de pé"),
    "velocidade_pct": st.column_config.TextColumn("Velocidade de vendas"),
}


def _config_para(df: pd.DataFrame, colunas: dict) -> dict:
    return {chave: valor for chave, valor in colunas.items() if chave in df.columns}


def grafico_barras(
    df: pd.DataFrame, coluna_categoria: str, coluna_valor: str, rotulo_eixo_y: str, rotulo_tooltip: str
) -> alt.Chart:
    """Gráfico de barras com tooltip mostrando o valor já formatado (ex.: 'Velocidade de vendas: 50,3%')."""
    df_grafico = df.copy()
    df_grafico["_tooltip"] = df_grafico[coluna_valor].apply(formatar_percentual_br)
    return (
        alt.Chart(df_grafico)
        .mark_bar(color="#70451F")
        .encode(
            x=alt.X(f"{coluna_categoria}:N", sort=list(df_grafico[coluna_categoria]), title=None),
            y=alt.Y(f"{coluna_valor}:Q", title=rotulo_eixo_y),
            tooltip=[
                alt.Tooltip(f"{coluna_categoria}:N", title="Empreendimento"),
                alt.Tooltip("_tooltip:N", title=rotulo_tooltip),
            ],
        )
        .properties(width=800, height=320)
    )


with aba1:
    st.subheader("Velocidade de vendas por empreendimento")
    st.caption(
        "Do total de unidades colocadas à venda em cada empreendimento, qual fatia já foi "
        "vendida e continua vendida (descontando os distratos)."
    )
    try:
        df_velocidade = calcular_velocidade_vendas()
    except Exception as e:
        df_velocidade = None
        st.error("Não foi possível calcular a velocidade de vendas agora. Tente novamente em instantes.")
        with st.expander("Detalhes técnicos"):
            st.caption(str(e))

    if df_velocidade is not None:
        if df_velocidade.empty:
            st.info("Nenhum empreendimento encontrado para calcular a velocidade de vendas.")
        else:
            df_ordenado = df_velocidade.sort_values("velocidade_pct", ascending=True)

            with st.container(border=True, key="exec-card-chart-velocidade"):
                with st.container(horizontal_alignment="center"):
                    st.altair_chart(
                        grafico_barras(
                            df_ordenado,
                            "empreendimento",
                            "velocidade_pct",
                            "Velocidade de vendas (%)",
                            "Velocidade de vendas",
                        )
                    )

            st.space("small")

            df_velocidade_fmt = formatar_colunas_br(
                df_ordenado,
                colunas_percentual=("velocidade_pct",),
                colunas_inteiro=("total_ofertado", "vendas_liquidas"),
            )

            with st.container(border=True, key="exec-card-table-velocidade"):
                st.markdown("**Os 3 empreendimentos que mais precisam de atenção**")
                st.dataframe(
                    df_velocidade_fmt.head(3),
                    column_config=_config_para(df_velocidade_fmt, COLUNAS_VELOCIDADE),
                    hide_index=True,
                )

            pior = df_ordenado.iloc[0]
            insight(
                f"<strong>{pior['empreendimento']}</strong> apresenta a menor velocidade de vendas "
                f"entre os empreendimentos analisados, com {formatar_percentual_br(pior['velocidade_pct'])} "
                "do estoque vendido e mantido.",
                "Priorizar investigação comercial e análise do estoque remanescente deste empreendimento.",
            )

            with st.expander("Ver todos os empreendimentos"):
                st.dataframe(
                    df_velocidade_fmt,
                    column_config=_config_para(df_velocidade_fmt, COLUNAS_VELOCIDADE),
                    hide_index=True,
                )

COLUNAS_ESTOURO = {
    "empreendimento": st.column_config.TextColumn("Empreendimento"),
    "custo_orcado_acumulado": st.column_config.TextColumn("Custo planejado"),
    "custo_realizado_acumulado": st.column_config.TextColumn("Custo já gasto"),
    "estouro_absoluto": st.column_config.TextColumn("Quanto passou do planejado (R$)"),
    "estouro_pct": st.column_config.TextColumn("Quanto passou do planejado (%)"),
}

with aba2:
    st.subheader("Risco de estouro de custo por empreendimento")
    st.caption("Compara quanto foi planejado gastar em cada obra com quanto já foi realmente gasto.")
    try:
        df_estouro = calcular_estouro_custo()
    except Exception as e:
        df_estouro = None
        st.error("Não foi possível calcular o estouro de custo agora. Tente novamente em instantes.")
        with st.expander("Detalhes técnicos"):
            st.caption(str(e))

    if df_estouro is not None:
        if df_estouro.empty:
            st.info("Nenhum dado de obra encontrado para calcular estouro de custo.")
        else:
            df_ordenado = df_estouro.sort_values("estouro_pct", ascending=False)

            with st.container(border=True, key="exec-card-chart-estouro"):
                with st.container(horizontal_alignment="center"):
                    st.altair_chart(
                        grafico_barras(
                            df_ordenado,
                            "empreendimento",
                            "estouro_pct",
                            "Estouro de custo (%)",
                            "Estouro de custo",
                        )
                    )

            st.space("small")

            df_estouro_fmt = formatar_colunas_br(
                df_ordenado,
                colunas_moeda=("custo_orcado_acumulado", "custo_realizado_acumulado", "estouro_absoluto"),
                colunas_percentual=("estouro_pct",),
            )

            em_risco = df_ordenado[df_ordenado["estouro_absoluto"] > 0]
            em_risco_fmt = df_estouro_fmt.loc[em_risco.index]
            if em_risco.empty:
                st.success("Nenhum empreendimento gastando acima do planejado no momento.")
            else:
                with st.container(border=True, key="exec-card-table-estouro"):
                    st.markdown(f"**{len(em_risco)} empreendimento(s) gastando acima do planejado**")
                    st.dataframe(
                        em_risco_fmt,
                        column_config=_config_para(em_risco_fmt, COLUNAS_ESTOURO),
                        hide_index=True,
                    )

                pior = em_risco.iloc[0]
                insight(
                    f"<strong>{pior['empreendimento']}</strong> é o empreendimento com maior estouro de "
                    f"custo, {formatar_percentual_br(pior['estouro_pct'])} acima do planejado "
                    f"({formatar_moeda_br(pior['estouro_absoluto'])} além do orçado).",
                    "Revisar o orçamento remanescente da obra e investigar a causa do desvio junto à "
                    "equipe de engenharia.",
                )

            with st.expander("Ver todos os empreendimentos"):
                st.dataframe(
                    df_estouro_fmt,
                    column_config=_config_para(df_estouro_fmt, COLUNAS_ESTOURO),
                    hide_index=True,
                )

with aba3:
    st.subheader("Clientes cadastrados em duplicidade")
    st.caption(
        "Consideramos duplicado um cadastro em que nome, cidade e data de cadastro são "
        "idênticos a outro — um critério rigoroso, para não apontar duplicidade onde não existe."
    )
    try:
        df_duplicados = calcular_clientes_duplicados()
    except Exception as e:
        df_duplicados = None
        st.error("Não foi possível verificar clientes duplicados agora. Tente novamente em instantes.")
        with st.expander("Detalhes técnicos"):
            st.caption(str(e))

    if df_duplicados is not None:
        if df_duplicados.empty:
            st.success("Nenhum cliente duplicado encontrado sob este critério.")
        else:
            with st.container(border=True, key="exec-card-table-duplicados"):
                st.markdown(f"**{len(df_duplicados)} registro(s) de possível duplicidade encontrados**")
                st.dataframe(df_duplicados, hide_index=True)

            insight(
                f"{len(df_duplicados)} registro(s) de cliente atendem ao critério rigoroso de "
                "duplicidade (nome, cidade e data de cadastro idênticos).",
                "Validar manualmente cada grupo antes de qualquer unificação de cadastro, já que a "
                "base não possui CPF ou telefone para uma deduplicação mais precisa.",
            )

COLUNAS_DIVERGENCIA = {
    "empreendimento": st.column_config.TextColumn("Empreendimento"),
    "mes_referencia": st.column_config.TextColumn("Mês"),
    "resultado_reportado": st.column_config.TextColumn("Resultado reportado"),
    "resultado_recalculado": st.column_config.TextColumn("Resultado recalculado"),
    "divergencia_abs": st.column_config.TextColumn("Diferença encontrada"),
    "inconsistente": st.column_config.CheckboxColumn("Acima do tolerado?"),
}

with aba4:
    st.subheader("Financeiro: o que foi reportado x o que os dados mostram")
    st.caption(
        "Comparamos o resultado reportado de cada mês com o valor recalculado a partir dos "
        "dados brutos. Diferenças de até R$ 1,00 são consideradas arredondamento, não erro."
    )
    try:
        df_divergencia = calcular_divergencia_financeira()
    except Exception as e:
        df_divergencia = None
        st.error("Não foi possível verificar a divergência financeira agora. Tente novamente em instantes.")
        with st.expander("Detalhes técnicos"):
            st.caption(str(e))

    if df_divergencia is not None:
        if df_divergencia.empty:
            st.info("Nenhum registro financeiro encontrado.")
        else:
            inconsistentes = df_divergencia[df_divergencia["inconsistente"]]
            total = len(df_divergencia)
            with st.container(horizontal=True):
                st.metric("Meses verificados", total, border=True)
                st.metric("Meses com diferença acima de R$ 1,00", len(inconsistentes), border=True)

            st.space("small")

            COLUNAS_MOEDA_DIVERGENCIA = ("resultado_reportado", "resultado_recalculado", "divergencia_abs")

            if inconsistentes.empty:
                st.success("Nenhuma divergência financeira acima do tolerado.")
            else:
                inconsistentes_ordenadas = inconsistentes.sort_values("divergencia_abs", ascending=False)
                inconsistentes_fmt = formatar_colunas_br(
                    inconsistentes_ordenadas, colunas_moeda=COLUNAS_MOEDA_DIVERGENCIA
                )
                with st.container(border=True, key="exec-card-table-divergencia"):
                    st.dataframe(
                        inconsistentes_fmt,
                        column_config=_config_para(inconsistentes_fmt, COLUNAS_DIVERGENCIA),
                        hide_index=True,
                    )

                pior = inconsistentes_ordenadas.iloc[0]
                insight(
                    f"O maior desvio está em <strong>{pior['empreendimento']}</strong>, no mês de "
                    f"{pior['mes_referencia']}, com diferença de {formatar_moeda_br(pior['divergencia_abs'])} "
                    "entre o resultado reportado e o recalculado.",
                    "Auditar o fechamento financeiro desse mês junto à equipe responsável pelo reporte.",
                )

            df_divergencia_fmt = formatar_colunas_br(df_divergencia, colunas_moeda=COLUNAS_MOEDA_DIVERGENCIA)
            with st.expander("Ver todos os meses (inclusive os sem divergência relevante)"):
                st.dataframe(
                    df_divergencia_fmt,
                    column_config=_config_para(df_divergencia_fmt, COLUNAS_DIVERGENCIA),
                    hide_index=True,
                )
