import re

from core.db import run_query


def validar_tabelas(sql: str) -> None:
    """
    Valida que toda tabela/view referenciada em FROM/JOIN existe de fato no banco.

    Bloqueia o padrão de alucinação mais comum de Text-to-SQL: o modelo inventa
    uma tabela plausível (ex.: "corretores", "leads", "reclamacoes") que soa
    razoável para o domínio de negócio mas não existe no schema real. Sem esta
    checagem, a query só falharia dentro de run_query() com um erro cru do
    SQLite (ou, pior, teria um nome coincidente com algo real e retornaria dado
    errado silenciosamente).

    Lê a lista de tabelas/views diretamente do sqlite_master (não duplica a
    string de schema do prompt) para nunca divergir do banco real.

    Levanta ValueError se alguma tabela/view referenciada não existir.
    """
    validas = {row["name"] for row in run_query("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}
    referenciadas = re.findall(r"\b(?:FROM|JOIN)\s+\"?'?(\w+)\"?'?", sql, flags=re.IGNORECASE)
    desconhecidas = sorted({r for r in referenciadas if r.upper() not in ("SELECT",)} - validas)
    if desconhecidas:
        raise ValueError(
            f"Query referencia tabela(s)/view(s) inexistente(s) no banco: {', '.join(desconhecidas)}"
        )


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
