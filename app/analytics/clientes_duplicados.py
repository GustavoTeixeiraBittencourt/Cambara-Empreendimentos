import pandas as pd

from core.db import run_query


def calcular() -> pd.DataFrame:
    """
    Identifica clientes duplicados pela regra 6:
    nome + cidade + data_cadastro todos idênticos entre dois ou mais registros.

    Nesta base, o resultado esperado é um DataFrame vazio com as colunas corretas —
    a função nunca retorna None nem levanta exceção por resultado vazio.

    Colunas retornadas: id, nome, cidade, data_cadastro.
    """
    rows = run_query(
        """
        SELECT id, nome, cidade, data_cadastro
        FROM clientes
        WHERE (nome, cidade, data_cadastro) IN (
            SELECT nome, cidade, data_cadastro
            FROM clientes
            GROUP BY nome, cidade, data_cadastro
            HAVING COUNT(*) > 1
        )
        ORDER BY nome, cidade, data_cadastro, id
        """
    )

    if not rows:
        return pd.DataFrame(columns=["id", "nome", "cidade", "data_cadastro"])

    return pd.DataFrame(rows, columns=["id", "nome", "cidade", "data_cadastro"])


def resumo_distorcao_potencial() -> dict:
    """
    Quantifica a pergunta de negócio "como isso distorceria uma métrica de
    clientes únicos ou de ticket médio por cliente, se não fosse tratado?"
    (regra 6): mede o efeito de um critério ingênuo de deduplicação (só por
    `nome`, sem `cidade`/`data_cadastro`) — o critério que a aplicação
    DELIBERADAMENTE NÃO usa (ver calcular()), mas que uma abordagem menos
    cuidadosa poderia adotar.

    Colunas: grupos_nome_repetido, registros_em_grupos_nome_repetido,
    reducao_potencial_clientes_unicos (registros - grupos, i.e. quantos
    cadastros seriam fundidos indevidamente), total_clientes,
    percentual_reducao_potencial.
    """
    grupos = run_query(
        "SELECT nome, COUNT(*) AS n FROM clientes GROUP BY nome HAVING COUNT(*) > 1"
    )
    total_grupos = len(grupos)
    registros_em_grupos = sum(g["n"] for g in grupos)
    total_clientes = run_query("SELECT COUNT(*) AS n FROM clientes")[0]["n"]
    reducao = registros_em_grupos - total_grupos

    return {
        "grupos_nome_repetido": total_grupos,
        "registros_em_grupos_nome_repetido": registros_em_grupos,
        "reducao_potencial_clientes_unicos": reducao,
        "total_clientes": total_clientes,
        "percentual_reducao_potencial": round(reducao / total_clientes * 100, 1) if total_clientes else 0,
    }
