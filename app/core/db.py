import os
import sqlite3
from contextlib import contextmanager

_DB_PATH = os.path.normpath(
    os.getenv(
        "DB_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "cambara_teste_tecnico.db"),
    )
)


def caminho_banco() -> str:
    """Caminho do arquivo de banco em uso (pode vir de DB_PATH, ex.: testes/auditoria)."""
    return _DB_PATH


def get_connection() -> sqlite3.Connection:
    """
    Abre conexão com row_factory=sqlite3.Row.

    PRAGMA foreign_keys=ON porque o SQLite, por padrão, NÃO aplica as
    cláusulas REFERENCES do schema (elas ficam decorativas sem esse pragma,
    por conexão) — sem isso, um cliente_id ou unidade_id inexistente seria
    aceito silenciosamente em qualquer INSERT/UPDATE. É defesa em profundidade:
    a camada de negócio (core/regras_negocio.py) já valida explicitamente
    essas referências antes de escrever, mas o pragma garante que nenhum
    caminho de escrita futuro reabra esse buraco sem querer.
    """
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_query(sql: str, params: tuple = ()) -> list[dict]:
    """Executa uma query de leitura e retorna lista de dicts."""
    conn = get_connection()
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@contextmanager
def transaction():
    """
    Context manager de transação: abre BEGIN IMMEDIATE, expõe cursor,
    faz COMMIT no sucesso e ROLLBACK em qualquer exceção.

    BEGIN IMMEDIATE (em vez de BEGIN/deferred) adquire o lock de escrita
    (RESERVED) já na abertura da transação, antes de qualquer SELECT dentro
    dela. Isso fecha uma janela de corrida real em registrar_venda/
    registrar_distrato: com BEGIN deferred, duas transações concorrentes
    podiam ambas fazer SELECT status/'disponivel' (ou esta_ativa()) antes de
    qualquer uma escrever — cada uma veria o estado "livre" e as duas
    prosseguiriam, resultando em duas vendas ativas para a mesma unidade (ou
    dois distratos), sem levantar nenhum erro. Com BEGIN IMMEDIATE, a segunda
    transação concorrente bloqueia até a primeira commitar/rollback e só então
    executa seu próprio SELECT — já vendo o estado atualizado, então a
    validação de negócio (UnidadeIndisponivelError/VendaJaDistratadaError)
    passa a de fato impedir o caso duplicado, em vez de só detectá-lo depois
    (unidades_com_dupla_venda_ativa, em core/validacoes.py).
    """
    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
