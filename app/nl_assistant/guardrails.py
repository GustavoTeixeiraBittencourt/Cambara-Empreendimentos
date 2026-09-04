import re


def validar_apenas_select(sql: str) -> None:
    """
    Valida que a query SQL gerada é apenas um SELECT.

    Levanta ValueError se:
    - a query (após remover espaços/comentários iniciais) não começar com SELECT (case-insensitive), OU
    - contiver ';' seguido de outro comando não-vazio (múltiplos statements).

    Chamada obrigatoriamente antes de qualquer execução de SQL gerado pelo assistente de NL.
    """
    # Remover comentários de linha (--) e de bloco (/* */) para checar o início real
    sem_comentarios = re.sub(r"--[^\n]*", " ", sql)
    sem_comentarios = re.sub(r"/\*.*?\*/", " ", sem_comentarios, flags=re.DOTALL)
    limpo = sem_comentarios.strip()

    if not re.match(r"^SELECT\b", limpo, flags=re.IGNORECASE):
        raise ValueError(
            f"Apenas queries SELECT são permitidas. Query recebida começa com: {limpo[:60]!r}"
        )

    # Verificar múltiplos statements (';' seguido de qualquer coisa que não seja só espaços)
    partes = re.split(r";", limpo)
    nao_vazias = [p.strip() for p in partes if p.strip()]
    if len(nao_vazias) > 1:
        raise ValueError(
            "Query contém múltiplos statements (;). Apenas um SELECT por vez é permitido."
        )
