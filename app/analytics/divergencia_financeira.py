import pandas as pd

from core.db import run_query


def calcular() -> pd.DataFrame:
    """
    Identifica divergências financeiras pela regra 7 (tolerância R$1,00).

    resultado_recalculado = receita_reconhecida - custo_incorrido - despesas_corporativas_rat
    divergencia_abs = abs(resultado_reportado - resultado_recalculado)
    inconsistente = divergencia_abs > 1.00

    Colunas retornadas:
    empreendimento, mes_referencia, resultado_reportado, resultado_recalculado,
    divergencia_abs, inconsistente.
    """
    rows = run_query(
        """
        SELECT e.nome AS empreendimento,
               f.mes_referencia,
               f.receita_reconhecida,
               f.custo_incorrido,
               f.despesas_corporativas_rat,
               f.resultado_reportado
        FROM financeiro_mensal f
        JOIN empreendimentos e ON e.id = f.empreendimento_id
        ORDER BY e.nome, f.mes_referencia
        """
    )

    result = []
    for r in rows:
        recalculado = (
            r["receita_reconhecida"]
            - r["custo_incorrido"]
            - r["despesas_corporativas_rat"]
        )
        div = abs(r["resultado_reportado"] - recalculado)
        result.append(
            {
                "empreendimento": r["empreendimento"],
                "mes_referencia": r["mes_referencia"],
                "resultado_reportado": round(r["resultado_reportado"], 2),
                "resultado_recalculado": round(recalculado, 2),
                "divergencia_abs": round(div, 2),
                "inconsistente": div > 1.0,
            }
        )

    return pd.DataFrame(
        result,
        columns=[
            "empreendimento",
            "mes_referencia",
            "resultado_reportado",
            "resultado_recalculado",
            "divergencia_abs",
            "inconsistente",
        ],
    )
