import hashlib

from core.db import run_query


def autenticar(email: str, senha: str) -> dict | None:
    """
    Autentica um usuário pelo e-mail e senha.

    Compara sha256(senha).hexdigest() com usuarios.senha_hash.
    Retorna {id, nome, email, papel} ou None se credenciais inválidas.
    """
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    rows = run_query(
        "SELECT id, nome, email, papel FROM usuarios WHERE email = ? AND senha_hash = ?",
        (email, senha_hash),
    )
    return rows[0] if rows else None
