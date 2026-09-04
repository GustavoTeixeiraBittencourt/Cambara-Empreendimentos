import os

from core.db import run_query
from nl_assistant.guardrails import validar_apenas_select

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

_SCHEMA = """
Schema do banco (SQLite):
  empreendimentos(id, nome, cidade, uf, tipo, modelo_negocio, vgv_estimado, data_lancamento, status, observacoes)
  unidades(id, empreendimento_id, identificador, tipo, area_privativa_m2, valor_tabela, status)
  clientes(id, nome, cidade, uf, perfil, data_cadastro, email)
  vendas(id, unidade_id, cliente_id, data_venda, valor_venda, forma_pagamento, status_venda, data_distrato)
  obra_andamento(id, empreendimento_id, mes_referencia, percentual_conclusao, custo_orcado_mes, custo_realizado_mes, observacoes)
  financeiro_mensal(id, empreendimento_id, mes_referencia, receita_reconhecida, custo_incorrido, despesas_corporativas_rat, resultado_reportado)
  usuarios(id, nome, email, papel, senha_hash)

Views já normalizadas (SEMPRE prefira estas às tabelas brutas para perguntas
sobre status de venda ou de unidade — evitam ter que reproduzir a normalização
de grafia/sinônimo em SQL a cada consulta):
  vw_vendas(id, unidade_id, cliente_id, data_venda, valor_venda, forma_pagamento,
            status_venda_original, data_distrato, status_venda_normalizado, venda_distratada)
    - status_venda_normalizado já é só 'ativa' ou 'distratada' (2 valores).
    - venda_distratada é 0/1, já aplica a precedência de data_distrato sobre o texto do status.
  vw_unidades(id, empreendimento_id, identificador, tipo, area_privativa_m2, valor_tabela,
              status_original, status_grafia_normalizada, status_categoria)
    - status_categoria já é só 'vendida', 'disponivel', 'reservada' ou 'distrato' (4 valores).

Regras importantes (só relevantes se usar unidades/vendas em vez das views acima):
- unidades.status e vendas.status_venda (tabelas brutas) têm grafias inconsistentes,
  inclusive com acento (ex.: "Disponível") — normalize antes de comparar.
- Uma venda está distratada se status_venda (normalizado) em ('distrato','distratada','cancelado') OU data_distrato IS NOT NULL.
- Categorias de status em unidades: vendida, disponivel (sem acento), reservada, distrato.
"""

_PROMPT_TEMPLATE = """\
Você é um assistente de consulta a banco de dados SQLite para uma empresa imobiliária.
Dado o schema abaixo, converta a pergunta do usuário em uma query SQL válida.
IMPORTANTE: retorne APENAS o SQL, sem explicação, sem markdown, sem bloco de código.
O SQL deve ser um único SELECT.

{schema}

Pergunta: {pergunta}
SQL:"""


def perguntar(pergunta: str) -> dict:
    """
    Converte uma pergunta em linguagem natural para SQL, executa e retorna resultado.

    Fluxo:
    1. Monta prompt com schema + pergunta.
    2. Chama API Groq.
    3. Valida com validar_apenas_select() antes de executar.
    4. Executa com run_query().
    5. Gera resposta curta em português.

    Retorna: {sql: str, resultado: list[dict], resposta_texto: str}.
    sql e resultado são sempre expostos para rastreabilidade.
    """
    if not _GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY não configurada. Defina a variável no arquivo .env para usar o assistente."
        )

    try:
        from groq import Groq
    except ImportError as exc:
        raise ImportError("Instale o pacote 'groq': pip install groq") from exc

    client = Groq(api_key=_GROQ_API_KEY)

    prompt = _PROMPT_TEMPLATE.format(schema=_SCHEMA, pergunta=pergunta)
    completion = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=700,
    )

    sql = completion.choices[0].message.content.strip()

    # Remover possíveis blocos de markdown que o modelo insistir em usar
    if sql.startswith("```"):
        linhas = sql.splitlines()
        sql = "\n".join(
            l for l in linhas if not l.startswith("```")
        ).strip()

    validar_apenas_select(sql)

    resultado = run_query(sql)

    # Resposta em português baseada no resultado
    n = len(resultado)
    if n == 0:
        resposta_texto = "Nenhum resultado encontrado para esta consulta."
    elif n == 1 and len(resultado[0]) == 1:
        chave, valor = next(iter(resultado[0].items()))
        resposta_texto = f"Resultado: {valor}"
    else:
        resposta_texto = f"Consulta retornou {n} registro(s)."

    return {"sql": sql, "resultado": resultado, "resposta_texto": resposta_texto}
