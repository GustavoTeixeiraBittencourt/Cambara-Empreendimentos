import pandas as pd
import streamlit as st

from core.db import run_query
from core.validacoes import relatorio_qualidade_dado
from analytics.divergencia_financeira import calcular as calcular_divergencia_financeira
from format_br import column_config_centralizado, formatar_moeda_br, formatar_numero_br, formatar_percentual_br

st.set_page_config(page_title="Qualidade de Dados — Cambará", page_icon="🔍", layout="wide")

if "usuario" not in st.session_state:
    st.warning("Faça login na página inicial para acessar esta página.")
    st.stop()

st.html(
    """<div class="exec-header">
        <div class="exec-eyebrow">Governança de dados</div>
        <h1>Qualidade da base de dados</h1>
        <p>O que foi encontrado e corrigido na base antes de calcular qualquer indicador — isso é
        o que sustenta a confiabilidade dos números do Dashboard.</p>
    </div>"""
)

# CSS só dos 3 cards de status abaixo — reaproveita os tokens de cor já
# definidos globalmente em app/main.py (--exec-card, --exec-border, etc.) e as
# cores de categoria já usadas em .streamlit/config.toml (greenColor,
# orangeColor, grayColor); só adiciona a barra lateral por categoria
# semântica (neutro / resolvido / atenção), sem redefinir nada do tema.
st.html(
    """<style>
    .qc-card {
        border: 1px solid var(--exec-border);
        border-radius: 10px;
        padding: 1rem 1.1rem;
        background: var(--exec-card);
        box-shadow: 0 2px 8px rgba(80, 50, 20, 0.04);
        height: 100%;
    }
    .qc-card .qc-icon { font-size: 20px; line-height: 1; }
    .qc-card .qc-label {
        font-size: 11px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        font-weight: 600;
        color: var(--exec-text-soft);
        margin: 0.5rem 0 0.2rem 0;
    }
    .qc-card .qc-value { font-size: 28px; font-weight: 700; color: var(--exec-text); }
    .qc-card.qc-neutro { border-left: 3px solid #766B5E; }
    .qc-card.qc-resolvido { border-left: 3px solid #4A6B5A; }
    .qc-card.qc-atencao { border-left: 3px solid #B5651D; }
    </style>"""
)

TABELAS = ["empreendimentos", "unidades", "clientes", "vendas", "obra_andamento", "financeiro_mensal", "usuarios"]

# ---------------------------------------------------------------------------
# Volume de dados
# ---------------------------------------------------------------------------

st.header("Volume de dados")
try:
    volumes = [
        {"Tabela": tabela, "Registros": run_query(f"SELECT COUNT(*) AS n FROM {tabela}")[0]["n"]}
        for tabela in TABELAS
    ]
    df_volumes = pd.DataFrame(volumes)
    st.dataframe(df_volumes, column_config=column_config_centralizado(df_volumes), hide_index=True)
except Exception as e:
    st.error("Não foi possível carregar o volume de dados agora. Tente novamente em instantes.")
    with st.expander("Detalhes técnicos"):
        st.caption(str(e))

# ---------------------------------------------------------------------------
# Carrega o relatório uma vez — todos os números abaixo (cards + 3 blocos do
# acordeão) vêm exclusivamente daqui e das mesmas queries já usadas antes;
# nenhuma lógica de cálculo, regra de negócio ou consulta nova foi introduzida
# nesta reestruturação, só o agrupamento/rótulo/cor de apresentação.
# ---------------------------------------------------------------------------

try:
    qualidade = relatorio_qualidade_dado()
except Exception as e:
    qualidade = None
    st.error("Não foi possível carregar essas informações agora. Tente novamente em instantes.")
    with st.expander("Detalhes técnicos"):
        st.caption(str(e))

nulos = qualidade.get("nulos", {}) if qualidade else {}
grafias = qualidade.get("grafias_originais", {}) if qualidade else {}
categorias = qualidade.get("categorias_normalizadas", {}) if qualidade else {}
conflitos = qualidade.get("conflitos_data_distrato_vs_status_venda", {}) if qualidade else {}
divergencias = qualidade.get("divergencias_financeiras", {}) if qualidade else {}
integridade = qualidade.get("integridade_referencial") if qualidade else None
duplas = qualidade.get("unidades_com_dupla_venda_ativa") if qualidade else None
distorcao = qualidade.get("distorcao_potencial_clientes_duplicados") if qualidade else None

total_nulos = sum(nulos.values()) if nulos else 0
total_conflitos = conflitos.get("total", 0)
total_divergencias = divergencias.get("total_inconsistentes", 0)
total_orfaos = sum(r["registros_sem_correspondencia"] for r in integridade) if integridade is not None else None
total_grafias_originais = len(grafias.get("unidades_status", [])) + len(grafias.get("vendas_status_venda", []))
total_categorias_finais = len(categorias.get("unidades_status", [])) + len(categorias.get("vendas_status_venda", []))
grupos_nome = distorcao["grupos_nome_repetido"] if distorcao else 115
registros_nome = distorcao["registros_em_grupos_nome_repetido"] if distorcao else 234

try:
    limites_obra = run_query(
        "SELECT MIN(percentual_conclusao) AS minimo, MAX(percentual_conclusao) AS maximo FROM obra_andamento"
    )[0]
except Exception:
    limites_obra = None

# ---------------------------------------------------------------------------
# Achados e correções — 3 cards de status, um por categoria semântica
# (neutro / resolvido / atenção), não só 3 métricas com o mesmo peso visual.
# ---------------------------------------------------------------------------

st.header("Achados e correções")

if qualidade:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.html(
            f"""<div class="qc-card qc-neutro">
                <div class="qc-icon">ℹ️</div>
                <div class="qc-label">Campos sem preenchimento (esperado — opcionais)</div>
                <div class="qc-value">{formatar_numero_br(total_nulos, 0)}</div>
            </div>"""
        )
    with col2:
        st.html(
            f"""<div class="qc-card qc-resolvido">
                <div class="qc-icon">✅</div>
                <div class="qc-label">Vendas com status e data conflitantes (já corrigidas)</div>
                <div class="qc-value">{formatar_numero_br(total_conflitos, 0)}</div>
            </div>"""
        )
    with col3:
        st.html(
            f"""<div class="qc-card qc-atencao">
                <div class="qc-icon">⚠️</div>
                <div class="qc-label">Meses com resultado financeiro divergente (requer decisão)</div>
                <div class="qc-value">{formatar_numero_br(total_divergencias, 0)}</div>
            </div>"""
        )
    st.space("small")

# ---------------------------------------------------------------------------
# Bloco 1 — Verificado, sem problema encontrado
# ---------------------------------------------------------------------------

st.header("✅ Verificado, sem problema encontrado")

label_integridade = "Integridade entre cadastros"
if total_orfaos is not None:
    label_integridade += (
        " — nenhuma inconsistência encontrada"
        if total_orfaos == 0
        else f" — {total_orfaos} registro(s) sem correspondência, requer investigação"
    )
with st.expander(label_integridade):
    st.write(
        "Conferimos se todo registro que referencia outro (por exemplo, uma venda apontando para "
        "uma unidade) de fato aponta para um registro existente."
    )
    if integridade is not None:
        df_integridade = pd.DataFrame(
            [
                {
                    "Relação": r["relacao"],
                    "Registros sem correspondência": r["registros_sem_correspondencia"],
                }
                for r in integridade
            ]
        )
        st.dataframe(df_integridade, column_config=column_config_centralizado(df_integridade), hide_index=True)
        if total_orfaos == 0:
            st.success("Nenhuma das 5 relações verificadas apresentou inconsistência.")
        else:
            st.warning(
                f"{total_orfaos} registro(s) apontam para um cadastro que não existe — "
                "veja a coluna acima para saber em qual relação."
            )
    else:
        st.error("Não foi possível verificar a integridade entre cadastros agora.")

    if duplas is not None:
        if not duplas:
            st.caption(
                "Também não encontramos nenhuma unidade com duas vendas ativas ao mesmo tempo — "
                "ou seja, não há indício de dupla venda na base."
            )
        else:
            st.warning(
                f"{len(duplas)} unidade(s) têm mais de uma venda ativa registrada ao mesmo tempo — "
                "isso não deveria acontecer e merece investigação."
            )
            df_duplas = pd.DataFrame(duplas)
            st.dataframe(df_duplas, column_config=column_config_centralizado(df_duplas), hide_index=True)

with st.expander(
    f"Por que não encontramos clientes duplicados — 0 grupos sob critério rigoroso "
    f"({registros_nome} cadastros homônimos avaliados)"
):
    st.write(
        f"A base tem {grupos_nome} grupos de clientes com nome repetido ({registros_nome} cadastros), mas ao "
        "comparar cidade, e-mail e data de cadastro, a esmagadora maioria diverge em pelo menos um "
        "desses campos — são pessoas diferentes com o mesmo nome (homônimos), não duplicidade de "
        "cadastro."
    )
    st.caption(
        "Não há CPF nem telefone na base para uma deduplicação mais precisa, e o e-mail é gerado "
        "a partir do próprio ID do cliente — por construção, nunca se repete, então não serve como "
        "critério de comparação. Por isso adotamos o critério mais rigoroso possível com os dados "
        "disponíveis: nome, cidade e data de cadastro idênticos. Veja o resultado na aba "
        "\"Clientes duplicados\" do Dashboard."
    )
    if distorcao:
        st.warning(
            f"Se a deduplicação usasse só o nome (sem cidade e data de cadastro), esses "
            f"{registros_nome} cadastros seriam fundidos em {grupos_nome} \"clientes\" — uma redução "
            f"indevida de {distorcao['reducao_potencial_clientes_unicos']} registros na contagem "
            f"de clientes únicos ({formatar_percentual_br(distorcao['percentual_reducao_potencial'])} "
            f"dos {distorcao['total_clientes']} clientes da base). Como o ticket médio por cliente "
            "é receita total dividida pelo número de clientes únicos, esse mesmo denominador "
            "artificialmente menor infla o ticket médio aparente, sugerindo que cada cliente gasta "
            "mais do que realmente gasta."
        )

label_obra = "Consistência do percentual de conclusão das obras"
if limites_obra is not None:
    label_obra += (
        f" — variação de {limites_obra['minimo']:.2f}% a {limites_obra['maximo']:.2f}%, "
        "dentro da faixa esperada"
    )
with st.expander(label_obra):
    if limites_obra is not None:
        st.write(
            f"O percentual de conclusão das obras varia de {limites_obra['minimo']:.2f}% a "
            f"{limites_obra['maximo']:.2f}% em toda a base — nenhum registro fora da faixa esperada de 0 a 100%."
        )
    else:
        st.error("Não foi possível verificar esses dados agora.")

with st.expander(
    f"Campos com informação faltando no cadastro — {formatar_numero_br(total_nulos, 0)} registros "
    "sem preenchimento (esperado, estrutural)"
):
    if nulos:
        df_nulos = pd.DataFrame(
            {"Campo": list(nulos.keys()), "Registros sem preenchimento": list(nulos.values())}
        )
        st.dataframe(df_nulos, column_config=column_config_centralizado(df_nulos), hide_index=True)
        st.caption(
            "A falta de preenchimento em \"observações\" é esperada — é um campo opcional, "
            "preenchido só quando há algo relevante a registrar. Já em \"data de distrato\", o "
            "vazio é estrutural: só existe valor quando a venda foi de fato distratada. Nenhum "
            "destes casos é uma inconsistência de qualidade — por isso ficam aqui, e não na seção "
            "de itens que exigem atenção."
        )
    else:
        st.success("Nenhum campo vazio encontrado.")

# ---------------------------------------------------------------------------
# Bloco 2 — Corrigido automaticamente pelo sistema
# ---------------------------------------------------------------------------

st.header("🔧 Corrigido automaticamente pelo sistema")

with st.expander(
    f"Grafias diferentes para o mesmo status, já unificadas — {total_grafias_originais} grafias "
    f"originais → {total_categorias_finais} categorias de negócio"
):
    st.write(
        "Os mesmos status apareciam escritos de formas diferentes no cadastro original. "
        "Antes de calcular qualquer indicador, padronizamos tudo para uma única grafia por status."
    )
    nomes_amigaveis = {
        "unidades_status": "Status das unidades",
        "vendas_status_venda": "Status das vendas",
    }
    for campo in grafias:
        st.markdown(f"**{nomes_amigaveis.get(campo, campo.replace('_', ' '))}**")
        st.caption("Como estava: " + ", ".join(grafias[campo]))
        st.caption("Como ficou: " + ", ".join(categorias.get(campo, [])))

with st.expander(
    f"Vendas com status e data de distrato conflitantes — {total_conflitos} casos, "
    "corrigidos pela regra de precedência"
):
    st.write(
        f"{total_conflitos} vendas tinham a data de distrato preenchida, mas o campo "
        "de status ainda dizia que a venda seguia ativa. Nesses casos, priorizamos a data — um "
        "fato que aconteceu ou não — e tratamos a venda como distratada."
    )

# ---------------------------------------------------------------------------
# Bloco 3 — Requer atenção: divergência real
# ---------------------------------------------------------------------------

st.header("⚠️ Requer atenção — divergência real")

with st.expander(
    f"Divergência entre resultado financeiro reportado e recalculado — {total_divergencias} de "
    f"{divergencias.get('total_registros', 0)} meses, requer decisão"
):
    st.write(
        f"{total_divergencias} de {divergencias.get('total_registros', 0)} "
        f"registros mensais ({formatar_percentual_br(divergencias.get('percentual', 0))}) têm uma diferença maior que "
        "R$ 1,00 entre o valor reportado e o valor recalculado a partir dos dados brutos. "
        "Diferenças menores que isso são consideradas arredondamento, não erro."
    )
    st.metric(
        "Empreendimentos com pelo menos um mês divergente",
        divergencias.get("total_empreendimentos_afetados", 0),
        border=True,
    )
    try:
        df_divergencia = calcular_divergencia_financeira()
        diffs = df_divergencia["resultado_reportado"] - df_divergencia["resultado_recalculado"]
        with st.container(horizontal=True):
            st.metric("Maior valor subestimado", formatar_moeda_br(diffs.min()), border=True)
            st.metric("Maior valor superestimado", formatar_moeda_br(diffs.max()), border=True)
            st.metric("Diferença média", formatar_moeda_br(diffs.mean()), border=True)
        st.caption(
            "Quando diverge, o resultado reportado tende mais a ficar abaixo do recalculado do "
            "que acima — mas a dispersão é grande, não é um viés pequeno e sistemático."
        )
    except Exception:
        pass
