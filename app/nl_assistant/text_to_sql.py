import os
import sqlite3

from core.db import run_query
from format_br import formatar_valor_heuristico as _formatar_valor
from nl_assistant.guardrails import validar_apenas_select, validar_tabelas

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Auditoria de 04/09/2026 (docs/roteiro_validacao_assistente.md): testado 20b vs
# 120b nesta mesma tarefa (geração de SQL). Em perguntas fora do schema (ex.:
# "corretor", "leads"), o 20b frequentemente esgotava o orçamento de tokens de
# raciocínio e devolvia string vazia (bloqueada por validar_apenas_select, mas
# sem nenhuma explicação útil); o 120b nunca fez isso e teve latência menor.
# Ambos alucinavam igualmente sem a instrução SEM_DADOS abaixo — o 120b foi
# escolhido pela confiabilidade de sempre produzir uma resposta (SQL ou
# SEM_DADOS), não por ser "melhor" em geral.
_MODELO = "openai/gpt-oss-120b"

_MARCADOR_SEM_DADOS = "SEM_DADOS:"

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

Regras de negócio importantes:
- unidades.status e vendas.status_venda (tabelas brutas) têm grafias inconsistentes,
  inclusive com acento (ex.: "Disponível") — normalize antes de comparar, ou prefira
  as views acima.
- Uma venda está distratada se status_venda (normalizado) em ('distrato','distratada','cancelado') OU data_distrato IS NOT NULL.
- Categorias de status em unidades: vendida, disponivel (sem acento), reservada, distrato.
- "Total ofertado" (denominador de velocidade de vendas) = COUNT(*) de TODAS as
  unidades cadastradas por empreendimento, SEM filtrar por status da unidade nem
  por status do empreendimento (nem mesmo excluir empreendimentos "Suspenso").
- "Velocidade de vendas" / "% vendido" de um empreendimento = (quantidade de
  VENDAS ATIVAS — linhas de vw_vendas com status_venda_normalizado = 'ativa' —
  ligadas a unidades daquele empreendimento) dividido pelo "total ofertado"
  acima. NÃO use unidades.status = 'vendida' como numerador: o status da
  unidade e a existência de uma venda ativa podem divergir; a definição de
  negócio é sempre pela tabela/view de vendas.
- clientes.nome, clientes.cidade e qualquer outra coluna de texto livre podem
  ter variação de maiúscula/minúscula ou espaço nas pontas — a base original
  é consistente, mas a tela "Vendas e Distratos" permite cadastrar cliente
  novo sem normalizar a digitação (ex.: "Matheus oliveira" em vez de "Matheus
  Oliveira"). Ao filtrar por um nome ou texto livre informado na pergunta,
  NUNCA use igualdade exata (=) sensível a maiúsculas — use LIKE '%valor%'
  (case-insensitive por padrão no SQLite para texto ASCII) para não deixar de
  encontrar um cliente só por causa da caixa ou de um espaço extra.
"""

_PROMPT_TEMPLATE = """\
Você é um assistente de consulta a banco de dados SQLite para uma empresa imobiliária.
Dado o schema abaixo, converta a pergunta do usuário em uma query SQL válida.

Regras OBRIGATÓRIAS:
- Retorne APENAS o SQL, sem explicação, sem markdown, sem bloco de código.
- O SQL deve ser um único SELECT.
- Prefira JOIN + GROUP BY direto (sem subquery/derived table) sempre que a
  pergunta puder ser respondida assim — é menos propenso a erro de digitação
  em nomes de coluna longos do que uma subquery aninhada com alias reaproveitado.
- NUNCA invente nome de tabela, coluna ou relacionamento (JOIN) que não esteja
  EXPLICITAMENTE listado no schema abaixo. Isso vale mesmo que o nome pareça óbvio
  ou provável (ex.: "corretor_id", "lead_id") — se não está no schema, não existe.
- Se a pergunta pedir um dado, entidade ou conceito que não existe neste schema
  (ex.: corretor, lead, reclamação de cliente, taxa de conversão por vendedor,
  ou qualquer métrica que exigiria uma coluna/tabela inexistente), NÃO tente
  aproximar nem devolver um valor substituto (como 0, NULL ou uma média geral
  sem o filtro pedido). Responda SOMENTE com a linha (sem mais nada):
  {marcador_sem_dados} <explicação curta de por que o schema não suporta a pergunta>
- Se a pergunta usar um termo de negócio (ex.: "lucro líquido", "receita") que
  não tem uma coluna com esse nome exato, mas o schema contém coluna(s) que
  claramente compõem esse conceito (ex.: financeiro_mensal já tem
  resultado_reportado, ou receita_reconhecida/custo_incorrido/despesas_
  corporativas_rat para recalculá-lo), USE essas colunas em vez de recusar —
  só use {marcador_sem_dados} quando o schema realmente não tiver nenhuma
  coluna que sustente o conceito pedido, não apenas por o nome não bater
  exatamente.
- Se a pergunta for atendível mas ambígua (mais de uma métrica/definição razoável
  cobre o termo usado, ex. "melhor desempenho"), escolha a interpretação mais
  literal e objetiva possível, com base nas regras de negócio acima, e prossiga
  — não use o marcador {marcador_sem_dados} só por ambiguidade.

{schema}

Pergunta: {pergunta}
SQL:"""


def _resumir_resultado(resultado: list[dict]) -> str:
    """
    Gera uma frase curta em português a partir do resultado real da query —
    puramente determinístico (sem chamada a LLM), para não introduzir risco de
    alucinação nesta etapa. Quando há mais de uma linha e é possível identificar
    uma coluna numérica e uma coluna de rótulo, destaca o maior valor — sempre
    lido diretamente das linhas retornadas pelo banco, nunca inventado.
    """
    n = len(resultado)
    if n == 0:
        return "Nenhum resultado encontrado para esta consulta."
    if n == 1 and len(resultado[0]) == 1:
        coluna, valor = next(iter(resultado[0].items()))
        return f"Resultado: {_formatar_valor(coluna, valor)}"
    if n == 1:
        pares = ", ".join(f"{k}: {_formatar_valor(k, v)}" for k, v in resultado[0].items())
        return f"Resultado: {pares}"

    colunas = list(resultado[0].keys())
    eh_identificador = lambda c: c == "id" or c.endswith("_id")  # noqa: E731
    colunas_numericas = [
        c
        for c in colunas
        if not eh_identificador(c)
        and all(isinstance(r.get(c), (int, float)) and not isinstance(r.get(c), bool) for r in resultado)
    ]
    # Rótulo precisa ser especificamente uma coluna de texto (ex.: nome do
    # empreendimento) — nunca "id"/"*_id": um identificador numérico exibido
    # como se fosse o rótulo (ex.: "(16)" em vez de "(Mirante Living)") é
    # tecnicamente extraído do resultado real, mas ilegível e confuso.
    colunas_rotulo = [
        c for c in colunas if not eh_identificador(c) and all(isinstance(r.get(c), str) for r in resultado)
    ]
    if colunas_numericas and colunas_rotulo:
        col_num, col_rotulo = colunas_numericas[0], colunas_rotulo[0]
        linha_maior = max(resultado, key=lambda r: r[col_num])
        return (
            f"Consulta retornou {n} registro(s). Maior valor de '{col_num}': "
            f"{_formatar_valor(col_num, linha_maior[col_num])} ({linha_maior[col_rotulo]})."
        )
    return f"Consulta retornou {n} registro(s)."


def perguntar(pergunta: str) -> dict:
    """
    Converte uma pergunta em linguagem natural para SQL, executa e retorna resultado.

    Fluxo:
    1. Monta prompt com schema + regras de negócio + pergunta.
    2. Chama API Groq (reasoning_effort="low" — tarefa mecânica de tradução para
       SQL não se beneficia de raciocínio longo, e o orçamento de tokens de
       raciocínio dos modelos gpt-oss em "default" às vezes consumia todo o
       max_tokens sem chegar a emitir o SQL; ver nota de auditoria acima).
    3. Se o modelo sinalizar SEM_DADOS (pergunta não respondível pelo schema),
       retorna essa explicação sem tentar nenhum SQL.
    4. Valida com validar_apenas_select() e validar_tabelas() antes de executar
       — a segunda bloqueia tabela/view inventada antes de tocar o banco.
    5. Executa com run_query(); erro de coluna/sintaxe do próprio SQLite (ex.:
       coluna inventada que validar_tabelas não pega, por estar numa tabela
       real) é capturado aqui e também vira uma recusa limpa, nunca uma
       exceção crua nem um valor inventado.
    6. Gera resposta curta em português — só a partir das linhas reais
       retornadas (_resumir_resultado), nunca por síntese de LLM.

    Retorna: {sql: str | None, resultado: list[dict] | None, resposta_texto: str}.
    sql e resultado são sempre expostos para rastreabilidade quando uma consulta
    de fato rodou; vêm None quando a pergunta foi recusada (SEM_DADOS ou erro).
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
    prompt = _PROMPT_TEMPLATE.format(schema=_SCHEMA, pergunta=pergunta, marcador_sem_dados=_MARCADOR_SEM_DADOS)
    mensagens = [{"role": "user", "content": prompt}]

    # Até 2 correções quando a query falha na execução (3 tentativas no
    # total). Achado de auditoria: o modelo comete esporadicamente um erro de
    # digitação isolado (ex.: "emprendimento_id" em vez de
    # "empreendimento_id") em ~15-20% das gerações. Reamostrar do zero com o
    # mesmo prompt original é pouco efetivo — o mesmo erro tende a se repetir
    # (chegou a reproduzir em 4/4 tentativas idênticas em temperature=0, e
    # ainda assim ocasionalmente em temperature=0.2). Em vez disso, cada
    # correção devolve o SQL que falhou + a mensagem de erro real do SQLite
    # na conversa (multi-turno) e pede o SQL corrigido — o modelo vê
    # exatamente qual identificador está errado, em vez de ter que acertar
    # de novo por sorte. Não corrige em caso de SEM_DADOS nem de SQL
    # bloqueado por validar_apenas_select/validar_tabelas — esses são
    # decisões do modelo sobre o que a pergunta pede, não erro de sintaxe.
    ultimo_erro_execucao = None
    for tentativa in range(3):
        completion = client.chat.completions.create(
            model=_MODELO,
            messages=mensagens,
            temperature=0.2,
            max_tokens=900,
            reasoning_effort="low",
        )

        sql = completion.choices[0].message.content.strip()

        # Remover possíveis blocos de markdown que o modelo insistir em usar
        if sql.startswith("```"):
            linhas = sql.splitlines()
            sql = "\n".join(
                l for l in linhas if not l.startswith("```")
            ).strip()

        if sql.startswith(_MARCADOR_SEM_DADOS):
            explicacao = sql[len(_MARCADOR_SEM_DADOS):].strip()
            resposta_texto = (
                "Não há dados suficientes na base para responder essa pergunta"
                + (f" ({explicacao})." if explicacao else ".")
            )
            return {"sql": None, "resultado": None, "resposta_texto": resposta_texto}

        validar_apenas_select(sql)
        validar_tabelas(sql)

        try:
            resultado = run_query(sql)
        except sqlite3.Error as exc:
            ultimo_erro_execucao = (sql, exc)
            mensagens.append({"role": "assistant", "content": sql})
            mensagens.append({
                "role": "user",
                "content": (
                    f"Essa query deu erro ao executar no SQLite: {exc}\n"
                    "Corrija a query e responda de novo SOMENTE com o SQL corrigido "
                    "(mesmas regras da mensagem original — sem explicação, sem markdown)."
                ),
            })
            continue

        resposta_texto = _resumir_resultado(resultado)
        return {"sql": sql, "resultado": resultado, "resposta_texto": resposta_texto}

    sql_final, _ = ultimo_erro_execucao
    return {
        "sql": sql_final,
        "resultado": None,
        "resposta_texto": "Não foi possível obter esse dado com as informações disponíveis no banco.",
    }
