import pandas as pd
import streamlit as st


def formatar_numero_br(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_br(valor: float, casas: int = 2) -> str:
    return f"R$ {formatar_numero_br(valor, casas)}"


def formatar_percentual_br(valor: float, casas: int = 1) -> str:
    return f"{formatar_numero_br(valor, casas)}%"


_PALAVRAS_MONETARIAS_HEURISTICO = (
    "valor", "receita", "custo", "despesa", "resultado", "ticket", "lucro",
    "faturamento", "divergencia", "orcado", "realizado", "_rat", "vgv", "estouro",
)
_PALAVRAS_PERCENTUAL_HEURISTICO = ("pct", "percentual")


def _eh_identificador(coluna: str) -> bool:
    return coluna == "id" or coluna.endswith("_id")


def formatar_valor_heuristico(coluna: str, valor):
    """
    Formata um valor no padrão numérico brasileiro a partir do nome da coluna
    (heurística por palavra-chave), para colunas que vêm de SQL gerado
    dinamicamente sem schema fixo conhecido de antemão (ex.: resultado bruto
    do assistente de linguagem natural). Colunas de identificador (id/"*_id")
    são deixadas intactas — não fazem sentido como moeda/percentual/milhar.
    Nunca falha: cai no formato numérico genérico quando o nome não sugere
    moeda nem percentual, e devolve o valor original se não for int/float.
    """
    if _eh_identificador(coluna):
        return valor
    if valor is None or isinstance(valor, bool):
        return str(valor)
    if not isinstance(valor, (int, float)):
        return str(valor)

    coluna_lower = coluna.lower()
    if any(p in coluna_lower for p in _PALAVRAS_MONETARIAS_HEURISTICO):
        return formatar_moeda_br(valor, 2)
    if any(p in coluna_lower for p in _PALAVRAS_PERCENTUAL_HEURISTICO):
        return formatar_percentual_br(valor, 1)
    if isinstance(valor, int):
        return formatar_numero_br(valor, 0)
    return formatar_numero_br(valor, 2)


def formatar_dataframe_heuristico(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna uma cópia do DataFrame com toda coluna numérica formatada no
    padrão brasileiro, classificando cada coluna por heurística de nome
    (formatar_valor_heuristico) — para tabelas de colunas desconhecidas de
    antemão, como o resultado bruto do assistente de linguagem natural.
    """
    df_formatado = df.copy()
    for coluna in df_formatado.columns:
        df_formatado[coluna] = df_formatado[coluna].apply(
            lambda v, c=coluna: formatar_valor_heuristico(c, v)
        )
    return df_formatado


def coluna_centralizada(config_existente: dict | None = None) -> dict:
    """
    Column_config de uma única coluna com alinhamento central, preservando o
    resto da configuração (rótulo, tipo, etc.) de uma coluna já definida via
    st.column_config (ex.: TextColumn/CheckboxColumn), se houver.
    """
    base = dict(config_existente) if config_existente else dict(st.column_config.Column())
    base["alignment"] = "center"
    return base


def column_config_centralizado(df: pd.DataFrame, colunas: dict | None = None) -> dict:
    """
    Monta o column_config para st.dataframe com TODAS as colunas do
    DataFrame centralizadas — por padrão o Streamlit alinha número à direita
    e texto à esquerda, o que deixa o dado colado na borda da célula.
    `colunas`, se informado, é um column_config já existente com rótulos/
    tipos customizados por coluna — a centralização é aplicada por cima,
    preservando o resto de cada coluna; colunas do DataFrame sem entrada em
    `colunas` também saem centralizadas, com configuração genérica.
    """
    colunas = colunas or {}
    return {coluna: coluna_centralizada(colunas.get(coluna)) for coluna in df.columns}


def formatar_colunas_br(
    df: pd.DataFrame,
    colunas_moeda: tuple = (),
    colunas_percentual: tuple = (),
    colunas_inteiro: tuple = (),
) -> pd.DataFrame:
    """Retorna uma cópia do DataFrame com as colunas indicadas convertidas
    para texto no padrão numérico brasileiro (milhar com ponto, decimal com
    vírgula), pronta para exibição em st.dataframe."""
    df_formatado = df.copy()
    for coluna in colunas_moeda:
        if coluna in df_formatado.columns:
            df_formatado[coluna] = df_formatado[coluna].apply(formatar_moeda_br)
    for coluna in colunas_percentual:
        if coluna in df_formatado.columns:
            df_formatado[coluna] = df_formatado[coluna].apply(formatar_percentual_br)
    for coluna in colunas_inteiro:
        if coluna in df_formatado.columns:
            df_formatado[coluna] = df_formatado[coluna].apply(lambda v: formatar_numero_br(v, 0))
    return df_formatado
