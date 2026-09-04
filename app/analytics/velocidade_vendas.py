import pandas as pd

from core.db import run_query
from core.regras_negocio import esta_ativa


def calcular() -> pd.DataFrame:
    """
    Calcula a velocidade de vendas por empreendimento.

    Regra 5: total_ofertado = todas as unidades cadastradas, sem filtrar por
    status do empreendimento.
    Regras 1-4: vendas_liquidas = vendas ativas (não distratadas).

    Colunas retornadas: empreendimento, total_ofertado, vendas_liquidas, velocidade_pct.
    """
    # Total ofertado por empreendimento (todas as unidades, sem filtro de status — regra 5)
    total_ofertado = run_query(
        """
        SELECT e.nome AS empreendimento, COUNT(u.id) AS total_ofertado
        FROM empreendimentos e
        JOIN unidades u ON u.empreendimento_id = e.id
        GROUP BY e.id, e.nome
        ORDER BY e.nome
        """
    )

    # Vendas com dados para aplicar as regras 1-4 em Python
    vendas = run_query(
        """
        SELECT v.unidade_id, v.status_venda, v.data_distrato,
               e.nome AS empreendimento
        FROM vendas v
        JOIN unidades u ON u.id = v.unidade_id
        JOIN empreendimentos e ON e.id = u.empreendimento_id
        """
    )

    # Vendas líquidas por empreendimento (apenas ativas — regras 1-4)
    liquidas: dict[str, int] = {}
    for v in vendas:
        if esta_ativa(v["status_venda"], v["data_distrato"]):
            liquidas[v["empreendimento"]] = liquidas.get(v["empreendimento"], 0) + 1

    rows = []
    for t in total_ofertado:
        emp = t["empreendimento"]
        tot = t["total_ofertado"]
        liq = liquidas.get(emp, 0)
        vel = round(liq / tot * 100, 2) if tot > 0 else 0.0
        rows.append(
            {
                "empreendimento": emp,
                "total_ofertado": tot,
                "vendas_liquidas": liq,
                "velocidade_pct": vel,
            }
        )

    return pd.DataFrame(rows, columns=["empreendimento", "total_ofertado", "vendas_liquidas", "velocidade_pct"])
