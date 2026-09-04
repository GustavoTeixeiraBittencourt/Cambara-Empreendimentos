from core.db import run_query
from core.regras_negocio import (
    categoria_status_unidade,
    esta_distratada,
    status_venda_normalizado,
)


def test_vw_vendas_existe_e_tem_todas_as_linhas():
    linhas = run_query("SELECT COUNT(*) AS n FROM vw_vendas")
    assert linhas[0]["n"] == 2206


def test_vw_vendas_bate_linha_a_linha_com_regra_python():
    linhas = run_query(
        """
        SELECT status_venda_original, data_distrato,
               status_venda_normalizado, venda_distratada
        FROM vw_vendas
        """
    )
    assert linhas
    for l in linhas:
        esperado_rotulo = status_venda_normalizado(l["status_venda_original"], l["data_distrato"])
        esperado_bool = esta_distratada(l["status_venda_original"], l["data_distrato"])
        assert l["status_venda_normalizado"] == esperado_rotulo, (
            f"venda com status_venda={l['status_venda_original']!r} data_distrato={l['data_distrato']!r}: "
            f"view={l['status_venda_normalizado']!r}, python={esperado_rotulo!r}"
        )
        assert bool(l["venda_distratada"]) == esperado_bool


def test_vw_vendas_so_tem_2_categorias():
    linhas = run_query("SELECT DISTINCT status_venda_normalizado FROM vw_vendas")
    categorias = {l["status_venda_normalizado"] for l in linhas}
    assert categorias == {"ativa", "distratada"}


def test_vw_unidades_existe_e_tem_todas_as_linhas():
    linhas = run_query("SELECT COUNT(*) AS n FROM vw_unidades")
    assert linhas[0]["n"] == 3300


def test_vw_unidades_bate_linha_a_linha_com_regra_python():
    linhas = run_query("SELECT status_original, status_categoria FROM vw_unidades")
    assert linhas
    for l in linhas:
        esperado = categoria_status_unidade(l["status_original"])
        assert l["status_categoria"] == esperado, (
            f"unidade com status={l['status_original']!r}: "
            f"view={l['status_categoria']!r}, python={esperado!r}"
        )


def test_vw_unidades_so_tem_4_categorias():
    linhas = run_query("SELECT DISTINCT status_categoria FROM vw_unidades")
    categorias = {l["status_categoria"] for l in linhas}
    assert categorias == {"vendida", "disponivel", "reservada", "distrato"}
