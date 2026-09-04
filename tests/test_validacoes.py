
from core.validacoes import relatorio_qualidade_dado


def test_categorias_normalizadas_vendas_e_unidades():
    qualidade = relatorio_qualidade_dado()
    categorias = qualidade["categorias_normalizadas"]

    assert categorias["vendas_status_venda"] == ["ativa", "distratada"]
    assert categorias["unidades_status"] == ["disponivel", "distrato", "reservada", "vendida"]


def test_conflitos_data_distrato_vs_status_venda_continua_37():
    qualidade = relatorio_qualidade_dado()
    assert qualidade["conflitos_data_distrato_vs_status_venda"]["total"] == 37


def test_integridade_referencial_sem_orfaos():
    """As 5 relações de FK do schema não devem ter registros órfãos na base
    entregue — verificação viva (consulta real), não um valor fixo no código
    (gap encontrado em revisão: a tela de Qualidade de Dados afirmava isso
    com uma lista [0, 0, 0, 0, 0] escrita à mão, não uma query)."""
    qualidade = relatorio_qualidade_dado()
    integridade = qualidade["integridade_referencial"]
    assert len(integridade) == 5
    assert all(r["registros_sem_correspondencia"] == 0 for r in integridade)


def test_sem_unidade_com_dupla_venda_ativa():
    qualidade = relatorio_qualidade_dado()
    assert qualidade["unidades_com_dupla_venda_ativa"] == []


def test_divergencia_financeira_18_empreendimentos_afetados():
    """Pergunta de negócio 4 pede 'em quantos meses/empreendimentos' a
    divergência ocorre — 63 meses (já coberto acima) em 18 empreendimentos
    distintos (ver docs/business_rule.md, regra 7, seção Validação)."""
    qualidade = relatorio_qualidade_dado()
    assert qualidade["divergencias_financeiras"]["total_empreendimentos_afetados"] == 18


def test_distorcao_potencial_clientes_duplicados():
    """Pergunta de negócio 3 pede para quantificar como a métrica de clientes
    únicos/ticket médio seria distorcida se a duplicidade não fosse tratada
    com o critério rigoroso (nome+cidade+data_cadastro) — 115 grupos de nome
    repetido, 234 cadastros, reduziriam 'clientes únicos' em 119 registros
    (4,4%) se fundidos por um critério ingênuo (só nome)."""
    qualidade = relatorio_qualidade_dado()
    distorcao = qualidade["distorcao_potencial_clientes_duplicados"]
    assert distorcao["grupos_nome_repetido"] == 115
    assert distorcao["registros_em_grupos_nome_repetido"] == 234
    assert distorcao["reducao_potencial_clientes_unicos"] == 119
    assert distorcao["total_clientes"] == 2691
