import pandas as pd

from core.db import run_query


def calcular() -> pd.DataFrame:
    """
    Calcula estouro de custo acumulado por empreendimento a partir de obra_andamento.

    Colunas retornadas:
    empreendimento, custo_orcado_acumulado, custo_realizado_acumulado,
    estouro_absoluto, estouro_pct.
    """
    rows = run_query(
        """
        SELECT e.nome AS empreendimento,
               SUM(o.custo_orcado_mes)     AS custo_orcado_acumulado,
               SUM(o.custo_realizado_mes)  AS custo_realizado_acumulado
        FROM obra_andamento o
        JOIN empreendimentos e ON e.id = o.empreendimento_id
        GROUP BY e.id, e.nome
        ORDER BY e.nome
        """
    )

    result = []
    for r in rows:
        orcado = r["custo_orcado_acumulado"] or 0.0
        realizado = r["custo_realizado_acumulado"] or 0.0
        estouro_abs = realizado - orcado
        estouro_pct = round(estouro_abs / orcado * 100, 2) if orcado != 0 else 0.0
        result.append(
            {
                "empreendimento": r["empreendimento"],
                "custo_orcado_acumulado": round(orcado, 2),
                "custo_realizado_acumulado": round(realizado, 2),
                "estouro_absoluto": round(estouro_abs, 2),
                "estouro_pct": estouro_pct,
            }
        )

    return pd.DataFrame(
        result,
        columns=[
            "empreendimento",
            "custo_orcado_acumulado",
            "custo_realizado_acumulado",
            "estouro_absoluto",
            "estouro_pct",
        ],
    )
