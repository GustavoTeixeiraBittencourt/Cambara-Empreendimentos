from collections import defaultdict

from analytics.clientes_duplicados import resumo_distorcao_potencial
from core.db import run_query
from core.regras_negocio import categoria_status_unidade, esta_ativa, status_venda_normalizado

# Relações de chave estrangeira verificadas por integridade_referencial().
# Nomes de tabela/coluna fixos (não vêm de entrada externa) — seguros para
# formatar direto na query.
_RELACOES_FK = [
    ("Unidade → Empreendimento", "unidades", "empreendimento_id", "empreendimentos"),
    ("Venda → Unidade", "vendas", "unidade_id", "unidades"),
    ("Venda → Cliente", "vendas", "cliente_id", "clientes"),
    ("Andamento de obra → Empreendimento", "obra_andamento", "empreendimento_id", "empreendimentos"),
    ("Financeiro mensal → Empreendimento", "financeiro_mensal", "empreendimento_id", "empreendimentos"),
]


def integridade_referencial() -> list[dict]:
    """
    Conta, para cada relação de chave estrangeira do schema, quantos registros
    apontam para um id que não existe na tabela referenciada.

    Existe porque o SQLite não aplica sozinho as cláusulas REFERENCES do
    schema sem PRAGMA foreign_keys=ON por conexão (ver core/db.py) — antes
    dessa correção, um cliente_id inválido podia ser gravado silenciosamente
    em vendas. Esta função dá ao painel de Qualidade de Dados uma checagem
    viva (consulta real), em vez de uma afirmação estática no código.

    Retorna: [{relacao, registros_sem_correspondencia}, ...], uma linha por
    relação verificada.
    """
    resultado = []
    for nome, tabela_origem, coluna_fk, tabela_destino in _RELACOES_FK:
        n = run_query(
            f"""
            SELECT COUNT(*) AS n
            FROM {tabela_origem} o
            LEFT JOIN {tabela_destino} d ON d.id = o.{coluna_fk}
            WHERE o.{coluna_fk} IS NOT NULL AND d.id IS NULL
            """
        )[0]["n"]
        resultado.append({"relacao": nome, "registros_sem_correspondencia": n})
    return resultado


def unidades_com_dupla_venda_ativa() -> list[dict]:
    """
    Lista unidades com mais de uma venda "ativa" simultânea (regra 4) — um
    estado que a camada de escrita não deveria permitir. Consulta real, para
    o painel de Qualidade de Dados não apenas afirmar que isso não acontece.

    Retorna: [{unidade_id, vendas_ativas_ids}, ...] — vazio quando não há
    nenhum caso (resultado esperado na base atual).
    """
    vendas = run_query("SELECT id, unidade_id, status_venda, data_distrato FROM vendas")
    por_unidade: dict[int, list[int]] = defaultdict(list)
    for v in vendas:
        if esta_ativa(v["status_venda"], v["data_distrato"]):
            por_unidade[v["unidade_id"]].append(v["id"])
    return [
        {"unidade_id": unidade_id, "vendas_ativas_ids": ids}
        for unidade_id, ids in por_unidade.items()
        if len(ids) > 1
    ]


def relatorio_qualidade_dado() -> dict:
    """
    Retorna os achados de qualidade de dado já fechados em docs/data_exploration.md:
    - nulos por tabela/coluna relevante
    - grafias distintas antes e depois da normalização (unidades.status, vendas.status_venda)
    - 37 casos de conflito data_distrato × status_venda (regra 3)
    - 63 casos de divergência financeira acima da tolerância (regra 7)

    Formato estruturado para a página de dashboard — sem reprocessar tudo na tela.
    """
    # Nulos em colunas relevantes (campos que têm nulos esperados e/ou significativos)
    nulos = {
        "empreendimentos.observacoes": run_query(
            "SELECT COUNT(*) AS n FROM empreendimentos WHERE observacoes IS NULL"
        )[0]["n"],
        "obra_andamento.observacoes": run_query(
            "SELECT COUNT(*) AS n FROM obra_andamento WHERE observacoes IS NULL"
        )[0]["n"],
        "vendas.data_distrato": run_query(
            "SELECT COUNT(*) AS n FROM vendas WHERE data_distrato IS NULL"
        )[0]["n"],
    }

    # Grafias distintas originais
    grafias_unidades = run_query("SELECT DISTINCT status FROM unidades")
    grafias_vendas = run_query("SELECT DISTINCT status_venda FROM vendas")

    # Categorias normalizadas resultantes.
    #
    # unidades.status: regras 1+2 (grafia + fusão "Cancelado"/"Distrato" → "distrato").
    # Corrigido em 03/09/2026 — antes esta linha usava só normalizar_status() (regra 1
    # isolada) e mostrava 5 valores (vendida, disponivel, reservada, distrato,
    # cancelado) em vez das 4 categorias de negócio que docs/business_rule.md
    # (regra 2, seção Validação) já afirmava como resultado esperado.
    categorias_unidades = sorted(
        set(categoria_status_unidade(r["status"]) for r in grafias_unidades)
    )
    # vendas.status_venda: regras 1+3 (grafia + fusão "distrato"/"distratada"/
    # "cancelado" → "distratada"). Corrigido em 03/09/2026 — antes esta linha usava
    # só normalizar_status() e mostrava 3 valores (ativa, distrato, distratada) em
    # vez de 2 ("distrato" e "distratada" não são variação de grafia, são
    # sinônimos — regra 3 já tratava isso via esta_distratada(), mas só como
    # booleano; esta linha não usava essa regra).
    categorias_vendas = sorted(
        set(status_venda_normalizado(r["status_venda"]) for r in grafias_vendas)
    )

    # 37 casos de conflito: data_distrato preenchida mas status_venda indica "ativa"
    conflitos_data_vs_status = run_query(
        """
        SELECT COUNT(*) AS n FROM vendas
        WHERE data_distrato IS NOT NULL
          AND LOWER(status_venda) IN ('ativa', 'ativo')
        """
    )[0]["n"]

    # Confirmação via regra 3 (mais preciso — usa esta_distratada)
    vendas = run_query("SELECT id, status_venda, data_distrato FROM vendas")
    conflitos_regra3 = [
        v for v in vendas
        if v["data_distrato"] is not None
        and status_venda_normalizado(v["status_venda"]) == "ativa"
    ]

    # 63 casos de divergência financeira > R$1,00 (regra 7)
    financeiro = run_query(
        """
        SELECT id, empreendimento_id, mes_referencia,
               receita_reconhecida, custo_incorrido, despesas_corporativas_rat,
               resultado_reportado
        FROM financeiro_mensal
        """
    )
    divergencias = []
    for r in financeiro:
        recalculado = (
            r["receita_reconhecida"]
            - r["custo_incorrido"]
            - r["despesas_corporativas_rat"]
        )
        div = abs(r["resultado_reportado"] - recalculado)
        if div > 1.0:
            divergencias.append(
                {
                    "id": r["id"],
                    "empreendimento_id": r["empreendimento_id"],
                    "mes_referencia": r["mes_referencia"],
                    "divergencia_abs": round(div, 2),
                }
            )

    return {
        "nulos": nulos,
        "grafias_originais": {
            "unidades_status": [r["status"] for r in grafias_unidades],
            "vendas_status_venda": [r["status_venda"] for r in grafias_vendas],
        },
        "categorias_normalizadas": {
            "unidades_status": categorias_unidades,
            "vendas_status_venda": categorias_vendas,
        },
        "conflitos_data_distrato_vs_status_venda": {
            "total": len(conflitos_regra3),
            "ids_afetados": [v["id"] for v in conflitos_regra3],
        },
        "divergencias_financeiras": {
            "total_inconsistentes": len(divergencias),
            "total_registros": len(financeiro),
            "percentual": round(len(divergencias) / len(financeiro) * 100, 1) if financeiro else 0,
            # Pergunta de negócio 4 pede explicitamente "em quantos meses/empreendimentos
            # isso ocorre" — total_inconsistentes já responde "quantos meses" (cada
            # linha de financeiro_mensal é um mês de um empreendimento); esta conta
            # responde a metade que faltava: quantos empreendimentos DISTINTOS têm
            # pelo menos um mês divergente.
            "total_empreendimentos_afetados": len({d["empreendimento_id"] for d in divergencias}),
        },
        "integridade_referencial": integridade_referencial(),
        "unidades_com_dupla_venda_ativa": unidades_com_dupla_venda_ativa(),
        # Pergunta de negócio 3 pede explicitamente "como isso distorceria uma
        # métrica de clientes únicos ou de ticket médio por cliente, se não fosse
        # tratado" — resumo_distorcao_potencial() quantifica essa contrafactual.
        "distorcao_potencial_clientes_duplicados": resumo_distorcao_potencial(),
    }
