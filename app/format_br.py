import pandas as pd


def formatar_numero_br(valor: float, casas: int = 2) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_br(valor: float, casas: int = 2) -> str:
    return f"R$ {formatar_numero_br(valor, casas)}"


def formatar_percentual_br(valor: float, casas: int = 1) -> str:
    return f"{formatar_numero_br(valor, casas)}%"


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
