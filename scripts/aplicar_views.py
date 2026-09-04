"""
Script de setup único — cria (ou recria) as views de normalização de status
(sql/views.sql: vw_vendas, vw_unidades) no banco SQLite. DDL puro, nunca altera
uma linha das tabelas originais (unidades, vendas).

Já foi rodado no banco entregue com o projeto — só é necessário rodar de novo se
você trocar data/cambara_teste_tecnico.db por uma cópia sem as views (ex.: um
reset a partir do dump original).

Uso:
    python scripts/aplicar_views.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "data", "cambara_teste_tecnico.db"),
)
_VIEWS_SQL_PATH = os.path.join(os.path.dirname(__file__), "..", "sql", "views.sql")


def main() -> None:
    with open(_VIEWS_SQL_PATH, "r", encoding="utf-8") as f:
        script = f.read()

    con = sqlite3.connect(_DB_PATH)
    try:
        con.executescript(script)
        con.commit()
        views = con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name"
        ).fetchall()
        integridade = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()

    print(f"Views aplicadas: {[v[0] for v in views]}")
    print(f"PRAGMA integrity_check: {integridade}")


if __name__ == "__main__":
    main()
