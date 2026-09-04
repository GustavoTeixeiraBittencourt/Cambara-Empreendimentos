"""
Script de setup único — roda uma vez para substituir o placeholder 'trocar_no_setup'
pelo hash SHA-256 da senha temporária documentada (regra 8).

Senha padrão: cambara2026

Uso:
    python scripts/setup_senhas.py
"""
import hashlib
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.db import run_query, transaction

SENHA_PADRAO = "cambara2026"


def main() -> None:
    placeholder = "trocar_no_setup"
    pendentes = run_query(
        "SELECT COUNT(*) AS n FROM usuarios WHERE senha_hash = ?", (placeholder,)
    )
    n = pendentes[0]["n"]
    if n == 0:
        print("Nenhum usuário com placeholder — setup já foi executado ou não é necessário.")
        return

    senha_hash = hashlib.sha256(SENHA_PADRAO.encode()).hexdigest()
    with transaction() as cur:
        cur.execute(
            "UPDATE usuarios SET senha_hash = ? WHERE senha_hash = ?",
            (senha_hash, placeholder),
        )
    print(f"{n} usuário(s) atualizados com hash SHA-256 da senha '{SENHA_PADRAO}'.")
    print(f"Hash gerado: {senha_hash}")


if __name__ == "__main__":
    main()
