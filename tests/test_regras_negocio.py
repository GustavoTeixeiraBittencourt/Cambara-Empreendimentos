
import threading

import pytest

from core.db import run_query, transaction
from core.exceptions import (
    ClienteInvalidoError,
    EmailJaCadastradoError,
    UnidadeIndisponivelError,
    UnidadeNaoEncontradaError,
    VendaJaDistratadaError,
    VendaNaoEncontradaError,
)
from core.regras_negocio import (
    categoria_status_unidade,
    esta_ativa,
    esta_distratada,
    normalizar_status,
    registrar_distrato,
    registrar_venda,
    status_venda_normalizado,
    unidades_disponiveis,
)


@pytest.mark.parametrize("entrada,esperado", [
    ("VENDIDA",    "vendida"),
    ("Vendida",    "vendida"),
    ("vendida",    "vendida"),
    ("Disponível", "disponivel"),
    ("DISPONIVEL", "disponivel"),
    ("disponivel", "disponivel"),
    ("Reservada",  "reservada"),
    ("reservada",  "reservada"),
    ("Distrato",   "distrato"),
    ("distrato",   "distrato"),
    ("Cancelado",  "cancelado"),
    ("Ativa",      "ativa"),
    ("ativa",      "ativa"),
    ("ATIVA",      "ativa"),
    ("Distratada", "distratada"),
])
def test_normalizar_status(entrada, esperado):
    assert normalizar_status(entrada) == esperado

@pytest.mark.parametrize("status_venda,data_distrato,esperado", [
    ("Ativa",      None,         False),
    ("ATIVA",      None,         False),
    ("ativa",      None,         False),
    # Caso crítico regra 3: data preenchida sobrepõe status "ativa"
    ("Ativa",      "2024-03-15", True),
    ("ATIVA",      "2024-01-01", True),
    # Categoria "distrato" em várias grafias
    ("Distrato",   None,         True),
    ("distrato",   None,         True),
    # Caso crítico regra 3: "Distratada" sem data_distrato — NÃO deve ser contado como ativa
    ("Distratada", None,         True),
    # Cancelado unificado (regras 2+3)
    ("Cancelado",  None,         True),
    # String vazia de data não conta como preenchida
    ("ativa",      "",           False),
])
def test_esta_distratada(status_venda, data_distrato, esperado):
    assert esta_distratada(status_venda, data_distrato) == esperado


def test_esta_ativa_e_inverso_de_esta_distratada():
    for sv, dd in [("Ativa", None), ("Distratada", None), ("ativa", "2024-01-01")]:
        assert esta_ativa(sv, dd) == (not esta_distratada(sv, dd))


# ---------------------------------------------------------------------------
# status_venda_normalizado — rótulo canônico revisado em 03/09/2026
# ("distrato" → "distratada", ver docs/business_rule.md regra 3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_venda,data_distrato,esperado", [
    ("Ativa",      None,          "ativa"),
    ("ATIVA",      None,          "ativa"),
    ("ativa",      None,          "ativa"),
    ("Distrato",   None,          "distratada"),
    ("distrato",   None,          "distratada"),
    ("Distratada", None,          "distratada"),
    ("Cancelado",  None,          "distratada"),
    # data_distrato preenchida tem precedência mesmo com texto "ativa" (regra 3)
    ("Ativa",      "2024-03-15",  "distratada"),
])
def test_status_venda_normalizado(status_venda, data_distrato, esperado):
    assert status_venda_normalizado(status_venda, data_distrato) == esperado


def test_categorias_finais_vendas_sao_apenas_ativa_e_distratada():
    """As 6 grafias brutas de vendas.status_venda devem colapsar para exatamente
    2 categorias de negócio — não 3 (bug corrigido em 03/09/2026 no painel de
    Qualidade de Dados, ver core/validacoes.py)."""
    vendas = run_query("SELECT status_venda, data_distrato FROM vendas")
    categorias = {status_venda_normalizado(v["status_venda"], v["data_distrato"]) for v in vendas}
    assert categorias == {"ativa", "distratada"}


# ---------------------------------------------------------------------------
# categoria_status_unidade — regras 1+2 (unidades.status), rótulo permanece
# "distrato" (não revisado — coluna e decisão de nomenclatura independentes
# de vendas.status_venda)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status,esperado", [
    ("VENDIDA",    "vendida"),
    ("Vendida",    "vendida"),
    ("Disponível", "disponivel"),
    ("DISPONIVEL", "disponivel"),
    ("Reservada",  "reservada"),
    ("Distrato",   "distrato"),
    ("distrato",   "distrato"),
    ("Cancelado",  "distrato"),
])
def test_categoria_status_unidade(status, esperado):
    assert categoria_status_unidade(status) == esperado


def test_categorias_finais_unidades_sao_exatamente_4():
    """11 grafias brutas de unidades.status devem colapsar para exatamente 4
    categorias de negócio (regra 2) — não 5 (bug corrigido em 03/09/2026 no
    painel de Qualidade de Dados, ver core/validacoes.py)."""
    unidades = run_query("SELECT status FROM unidades")
    categorias = {categoria_status_unidade(u["status"]) for u in unidades}
    assert categorias == {"vendida", "disponivel", "reservada", "distrato"}


# ---------------------------------------------------------------------------
# Contagens contra o banco real (regras 3 e 4)
# ---------------------------------------------------------------------------

def test_conflitos_data_distrato_vs_status_venda():
    """37 registros têm data_distrato preenchida mas status_venda 'ativa' (regra 3)."""
    vendas = run_query("SELECT status_venda, data_distrato FROM vendas")
    conflitos = [
        v for v in vendas
        if v["data_distrato"] is not None
        and normalizar_status(v["status_venda"]) in {"ativa", "ativo"}
    ]
    assert len(conflitos) == 37


def test_contagem_vendas_ativas():
    """Vendas ativas + distratadas devem somar o total de 2206 vendas."""
    vendas = run_query("SELECT status_venda, data_distrato FROM vendas")
    ativas = sum(1 for v in vendas if esta_ativa(v["status_venda"], v["data_distrato"]))
    distratadas = sum(1 for v in vendas if esta_distratada(v["status_venda"], v["data_distrato"]))
    assert ativas + distratadas == len(vendas) == 2206


# ---------------------------------------------------------------------------
# unidades_disponiveis
# ---------------------------------------------------------------------------

def test_unidades_disponiveis_total():
    """315 + 298 + 298 = 911 unidades disponíveis."""
    disponiveis = unidades_disponiveis()
    assert len(disponiveis) == 911


def test_unidades_disponiveis_filtro_empreendimento():
    """Filtragem por empreendimento retorna subconjunto das 911."""
    todas = unidades_disponiveis()
    emp_ids = {r["empreendimento_id"] for r in todas}
    for emp_id in list(emp_ids)[:3]:
        filtrado = unidades_disponiveis(empreendimento_id=emp_id)
        assert all(r["empreendimento_id"] == emp_id for r in filtrado)
        assert len(filtrado) <= len(todas)


def test_unidades_disponiveis_sem_status_indisponivel():
    """Nenhuma unidade retornada deve ter status normalizado != 'disponivel'."""
    for r in unidades_disponiveis():
        assert normalizar_status(r["status"]) == "disponivel"


# ---------------------------------------------------------------------------
# registrar_venda e registrar_distrato — testes com limpeza do banco
# ---------------------------------------------------------------------------

@pytest.fixture
def unidade_disponivel_id():
    """Retorna o id de uma unidade disponível para teste."""
    disponiveis = unidades_disponiveis()
    assert disponiveis, "Banco precisa ter ao menos uma unidade disponível"
    return disponiveis[0]["id"]


@pytest.fixture
def cliente_existente_id():
    return run_query("SELECT id FROM clientes LIMIT 1")[0]["id"]


@pytest.fixture
def venda_teste(unidade_disponivel_id, cliente_existente_id):
    """Cria uma venda de teste e faz limpeza após o teste."""
    resultado = registrar_venda(
        unidade_id=unidade_disponivel_id,
        cliente_id=cliente_existente_id,
        cliente_novo=None,
        data_venda="2026-09-03",
        valor_venda=500_000.0,
        forma_pagamento="Financiamento",
    )
    status_original = run_query(
        "SELECT status FROM unidades WHERE id=?", (unidade_disponivel_id,)
    )[0]["status"]
    yield resultado, unidade_disponivel_id, status_original

    # Limpeza: remover venda de teste e restaurar status da unidade
    with transaction() as cur:
        cur.execute("DELETE FROM vendas WHERE id=?", (resultado["venda_id"],))
        # Restaurar para 'disponivel' — valor normalizado confirmado no banco
        cur.execute("UPDATE unidades SET status='disponivel' WHERE id=?", (unidade_disponivel_id,))


def test_registrar_venda_sucesso(venda_teste):
    resultado, unidade_id, _ = venda_teste
    venda_id = resultado["venda_id"]

    venda = run_query("SELECT * FROM vendas WHERE id=?", (venda_id,))[0]
    uni = run_query("SELECT status FROM unidades WHERE id=?", (unidade_id,))[0]

    assert venda["status_venda"] == "ativa"
    assert venda["data_distrato"] is None
    assert uni["status"] == "vendida"
    assert resultado["unidade_id"] == unidade_id


def test_registrar_venda_unidade_indisponivel(unidade_disponivel_id, cliente_existente_id):
    """Tentar vender uma unidade que não está disponível deve levantar UnidadeIndisponivelError."""
    # Usar uma unidade que já está vendida (pegar qualquer uma)
    vendida = run_query(
        "SELECT id FROM unidades WHERE LOWER(status) = 'vendida' LIMIT 1"
    )
    assert vendida, "Banco precisa ter ao menos uma unidade vendida"
    with pytest.raises(UnidadeIndisponivelError):
        registrar_venda(
            unidade_id=vendida[0]["id"],
            cliente_id=cliente_existente_id,
            cliente_novo=None,
            data_venda="2026-09-03",
            valor_venda=1.0,
            forma_pagamento="Financiamento",
        )


def test_registrar_venda_unidade_inexistente(cliente_existente_id):
    """Unidade com id que não existe deve levantar UnidadeNaoEncontradaError
    (distinto de UnidadeIndisponivelError, usado quando a unidade existe mas
    está com outro status)."""
    with pytest.raises(UnidadeNaoEncontradaError):
        registrar_venda(
            unidade_id=999_999_999,
            cliente_id=cliente_existente_id,
            cliente_novo=None,
            data_venda="2026-09-03",
            valor_venda=1.0,
            forma_pagamento="Financiamento",
        )


def test_registrar_venda_cliente_inexistente(unidade_disponivel_id):
    """cliente_id que não corresponde a nenhum cliente cadastrado deve ser
    recusado pelo backend (não só filtrado pela tela) — gap encontrado em
    revisão: antes desta correção, a venda era gravada com um cliente_id
    inválido, sem nenhum erro."""
    with pytest.raises(ClienteInvalidoError):
        registrar_venda(
            unidade_id=unidade_disponivel_id,
            cliente_id=999_999_999,
            cliente_novo=None,
            data_venda="2026-09-03",
            valor_venda=1.0,
            forma_pagamento="Financiamento",
        )
    # A unidade não deve ter sido alterada pela tentativa rejeitada.
    status = run_query(
        "SELECT status FROM unidades WHERE id=?", (unidade_disponivel_id,)
    )[0]["status"]
    assert normalizar_status(status) == "disponivel"


def test_registrar_venda_sem_cliente_id_nem_cliente_novo(unidade_disponivel_id):
    """Nem cliente_id nem cliente_novo informados deve ser recusado, não
    gravar uma venda com cliente_id nulo."""
    with pytest.raises(ClienteInvalidoError):
        registrar_venda(
            unidade_id=unidade_disponivel_id,
            cliente_id=None,
            cliente_novo=None,
            data_venda="2026-09-03",
            valor_venda=1.0,
            forma_pagamento="Financiamento",
        )


def test_registrar_venda_valor_invalido(unidade_disponivel_id, cliente_existente_id):
    """valor_venda <= 0 deve ser recusado antes de qualquer escrita."""
    with pytest.raises(ValueError):
        registrar_venda(
            unidade_id=unidade_disponivel_id,
            cliente_id=cliente_existente_id,
            cliente_novo=None,
            data_venda="2026-09-03",
            valor_venda=0.0,
            forma_pagamento="Financiamento",
        )
    status = run_query(
        "SELECT status FROM unidades WHERE id=?", (unidade_disponivel_id,)
    )[0]["status"]
    assert normalizar_status(status) == "disponivel"


def test_registrar_venda_email_ja_cadastrado(unidade_disponivel_id):
    """E-mail de cliente novo que já pertence a outro cliente cadastrado deve
    ser recusado (EmailJaCadastradoError) — nem a venda nem o cliente
    duplicado podem ser gravados."""
    email_existente = run_query(
        "SELECT email FROM clientes WHERE email IS NOT NULL AND email != '' LIMIT 1"
    )[0]["email"]
    total_clientes_antes = run_query("SELECT COUNT(*) AS n FROM clientes")[0]["n"]
    total_vendas_antes = run_query("SELECT COUNT(*) AS n FROM vendas")[0]["n"]

    cliente_novo = {
        "nome": "Cliente Email Duplicado Teste",
        "cidade": "Curitiba",
        "uf": "PR",
        "perfil": "Investidor",
        "email": email_existente,
    }
    with pytest.raises(EmailJaCadastradoError):
        registrar_venda(
            unidade_id=unidade_disponivel_id,
            cliente_id=None,
            cliente_novo=cliente_novo,
            data_venda="2026-09-03",
            valor_venda=1.0,
            forma_pagamento="Financiamento",
        )

    assert run_query("SELECT COUNT(*) AS n FROM clientes")[0]["n"] == total_clientes_antes
    assert run_query("SELECT COUNT(*) AS n FROM vendas")[0]["n"] == total_vendas_antes
    status = run_query("SELECT status FROM unidades WHERE id=?", (unidade_disponivel_id,))[0]["status"]
    assert normalizar_status(status) == "disponivel"


def test_registrar_venda_email_vazio_nao_conflita(unidade_disponivel_id):
    """E-mail em branco no cliente novo não deve disparar
    EmailJaCadastradoError (campo é opcional na tela)."""
    cliente_novo = {
        "nome": "Cliente Sem Email Teste",
        "cidade": "Curitiba",
        "uf": "PR",
        "perfil": "Investidor",
        "email": "",
    }
    resultado = registrar_venda(
        unidade_id=unidade_disponivel_id,
        cliente_id=None,
        cliente_novo=cliente_novo,
        data_venda="2026-09-03",
        valor_venda=300_000.0,
        forma_pagamento="À vista",
    )
    try:
        cliente = run_query("SELECT * FROM clientes WHERE id=?", (resultado["cliente_id"],))
        assert cliente, "Cliente sem e-mail deve ter sido inserido normalmente"
    finally:
        with transaction() as cur:
            cur.execute("DELETE FROM vendas WHERE id=?", (resultado["venda_id"],))
            cur.execute("DELETE FROM clientes WHERE id=?", (resultado["cliente_id"],))
            cur.execute("UPDATE unidades SET status='disponivel' WHERE id=?", (unidade_disponivel_id,))


def test_registrar_venda_cliente_novo(unidade_disponivel_id):
    """Registrar venda com cliente_novo insere o cliente e usa o novo id."""
    cliente_novo = {
        "nome": "Cliente Teste Temporario",
        "cidade": "Curitiba",
        "uf": "PR",
        "perfil": "Investidor",
        "email": "teste.tmp@exemplo.com",
    }
    resultado = registrar_venda(
        unidade_id=unidade_disponivel_id,
        cliente_id=None,
        cliente_novo=cliente_novo,
        data_venda="2026-09-03",
        valor_venda=300_000.0,
        forma_pagamento="À vista",
    )
    try:
        cliente = run_query("SELECT * FROM clientes WHERE id=?", (resultado["cliente_id"],))
        assert cliente, "Cliente novo deve ter sido inserido"
        assert cliente[0]["nome"] == "Cliente Teste Temporario"
    finally:
        with transaction() as cur:
            cur.execute("DELETE FROM vendas WHERE id=?", (resultado["venda_id"],))
            cur.execute("DELETE FROM clientes WHERE id=?", (resultado["cliente_id"],))
            cur.execute("UPDATE unidades SET status='disponivel' WHERE id=?", (unidade_disponivel_id,))


def test_registrar_distrato_sucesso(venda_teste):
    resultado_venda, unidade_id, _ = venda_teste
    venda_id = resultado_venda["venda_id"]

    resultado_distrato = registrar_distrato(venda_id=venda_id, data_distrato="2026-09-03")

    venda = run_query("SELECT * FROM vendas WHERE id=?", (venda_id,))[0]
    uni = run_query("SELECT status FROM unidades WHERE id=?", (unidade_id,))[0]

    # Rótulo canônico revisado em 03/09/2026 (era "distrato", ver regra 3)
    assert venda["status_venda"] == "distratada", f"Esperado 'distratada', obtido '{venda['status_venda']}'"
    assert venda["data_distrato"] == "2026-09-03"
    # Regra 9: unidade vira "distrato", NÃO "disponivel" (coluna de unidades não
    # afetada pela revisão de nomenclatura de vendas.status_venda)
    assert uni["status"] == "distrato", f"Esperado 'distrato', obtido '{uni['status']}'"
    assert resultado_distrato["novo_status_unidade"] == "distrato"


def test_registrar_distrato_ja_distratada(venda_teste):
    resultado_venda, unidade_id, _ = venda_teste
    venda_id = resultado_venda["venda_id"]

    registrar_distrato(venda_id=venda_id, data_distrato="2026-09-03")
    with pytest.raises(VendaJaDistratadaError):
        registrar_distrato(venda_id=venda_id, data_distrato="2026-09-04")


def test_registrar_distrato_venda_inexistente():
    with pytest.raises(VendaNaoEncontradaError):
        registrar_distrato(venda_id=999_999_999, data_distrato="2026-09-03")


# ---------------------------------------------------------------------------
# Concorrência — BEGIN IMMEDIATE (core/db.py::transaction())
# ---------------------------------------------------------------------------

def test_registrar_venda_concorrencia_nao_duplica_venda(unidade_disponivel_id, cliente_existente_id):
    """Duas tentativas concorrentes de vender a MESMA unidade: transaction()
    usa BEGIN IMMEDIATE para serializar as transações de escrita, então a
    segunda thread só deve ler o status da unidade depois que a primeira já
    comitou. Resultado esperado: exatamente uma venda tem sucesso, a outra é
    recusada com UnidadeIndisponivelError — nunca as duas com sucesso (o que
    violaria a regra 4, criando duas vendas ativas para a mesma unidade)."""
    resultados = []
    erros = []
    lock = threading.Lock()

    def tentar():
        try:
            r = registrar_venda(
                unidade_id=unidade_disponivel_id,
                cliente_id=cliente_existente_id,
                cliente_novo=None,
                data_venda="2026-09-03",
                valor_venda=100_000.0,
                forma_pagamento="Financiamento",
            )
            with lock:
                resultados.append(r)
        except UnidadeIndisponivelError as e:
            with lock:
                erros.append(e)

    threads = [threading.Thread(target=tentar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(resultados) == 1, f"Esperado 1 sucesso, obtido {len(resultados)} (race condition não fechada)"
    assert len(erros) == 1, f"Esperado 1 recusa, obtido {len(erros)}"

    # Limpeza
    venda_id = resultados[0]["venda_id"]
    with transaction() as cur:
        cur.execute("DELETE FROM vendas WHERE id=?", (venda_id,))
        cur.execute("UPDATE unidades SET status='disponivel' WHERE id=?", (unidade_disponivel_id,))


# ---------------------------------------------------------------------------
# PRAGMA foreign_keys — defesa em profundidade (core/db.py)
# ---------------------------------------------------------------------------

def test_conexao_aplica_foreign_keys():
    """SQLite não aplica REFERENCES do schema sem este pragma por conexão —
    sem ele, um cliente_id inválido é aceito silenciosamente em INSERT."""
    from core.db import get_connection

    conn = get_connection()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()
