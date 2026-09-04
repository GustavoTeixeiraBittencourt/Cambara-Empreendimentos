import json
import os
from collections import Counter

from analytics.clientes_duplicados import calcular as calcular_clientes_duplicados
from analytics.divergencia_financeira import calcular as calcular_divergencia_financeira
from analytics.estouro_custo import calcular as calcular_estouro_custo
from analytics.velocidade_vendas import calcular as calcular_velocidade_vendas
from core.regras_negocio import unidades_disponiveis
from core.validacoes import relatorio_qualidade_dado

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# Independente do modelo usado por nl_assistant.text_to_sql (que tem sua
# própria constante _MODELO, hardcoded na chamada da API até a auditoria de
# 04/09/2026 — ver docs/roteiro_validacao_assistente.md). Este _MODELO aqui só
# interpreta o resumo JSON já calculado (nunca vê schema/SQL/dado bruto), onde
# o risco de alucinação de schema não existe — o 20b é suficiente e mais
# barato/rápido para essa tarefa.
_MODELO = "openai/gpt-oss-20b"

PERGUNTAS_SUGERIDAS = [
    "Quais empreendimentos precisam de atenção?",
    "Como está a velocidade de vendas?",
    "Existem problemas de qualidade nos dados?",
    "Quais são os principais insights?",
]

_MARCADOR_CONSULTA_SQL = "CONSULTA_SQL:"

_SYSTEM_PROMPT = f"""\
Você é o Assistente de Análise de Negócio do painel executivo da Cambará Empreendimentos.
Seu papel é ajudar a diretoria a interpretar os indicadores já calculados pelo sistema.

Regras importantes:
- Responda SOMENTE com base nos dados estruturados fornecidos a seguir. Nunca invente ou
  estime números que não estejam presentes nesses dados.
- Se a pergunta pedir uma contagem, lista, valor específico ou qualquer outro dado bruto
  que NÃO esteja nos dados estruturados fornecidos, NÃO diga que a informação está
  indisponível. Em vez disso, responda SOMENTE com a linha (sem mais nada):
  {_MARCADOR_CONSULTA_SQL} <pergunta reformulada para consulta ao banco de dados>
- NUNCA misture indicadores de domínios diferentes para responder a uma pergunta
  sobre outro domínio (ex.: não use "estouro de custo" ou dispersão de
  "velocidade de vendas" como se fossem evidência de problema de qualidade de
  dado — são conceitos diferentes, cada um com seu próprio indicador nos dados
  fornecidos). Se o domínio exato perguntado não estiver nos dados estruturados
  E não for um dado bruto consultável (ou seja, não se aplica o CONSULTA_SQL
  acima), diga claramente que não tem esse indicador disponível no momento.
- NUNCA invente uma causa ou explicação (ex.: "isso indica erro de coleta de
  dados") que não esteja literalmente presente nos dados estruturados
  fornecidos. Relate os números; se for interpretar, deixe explícito que é uma
  leitura executiva sua, não um fato dos dados.
- Se usar um indicador para responder a um termo ambíguo da pergunta (ex.:
  responder "desempenho" ou "vendeu mais" usando velocidade de vendas), diga
  qual indicador usou — não deixe implícito que é a única leitura possível.
- Seja executivo: direto, conciso, em português, poucos parágrafos curtos ou uma lista curta.
"""


def _resumo_velocidade_vendas() -> dict:
    df = calcular_velocidade_vendas()
    if df.empty:
        return {"disponivel": False}
    ordenado = df.sort_values("velocidade_pct")
    pior = ordenado.iloc[0]
    melhor = ordenado.iloc[-1]
    return {
        "disponivel": True,
        "media_velocidade_pct": round(df["velocidade_pct"].mean(), 1),
        "pior_empreendimento": pior["empreendimento"],
        "pior_velocidade_pct": pior["velocidade_pct"],
        "melhor_empreendimento": melhor["empreendimento"],
        "melhor_velocidade_pct": melhor["velocidade_pct"],
    }


def _resumo_estouro_custo() -> dict:
    df = calcular_estouro_custo()
    if df.empty:
        return {"disponivel": False}
    em_risco = df[df["estouro_absoluto"] > 0].sort_values("estouro_pct", ascending=False)
    resumo = {"disponivel": True, "total_empreendimentos_em_risco": len(em_risco)}
    if not em_risco.empty:
        pior = em_risco.iloc[0]
        resumo["pior_empreendimento"] = pior["empreendimento"]
        resumo["pior_estouro_pct"] = pior["estouro_pct"]
        resumo["pior_estouro_absoluto_reais"] = pior["estouro_absoluto"]
    return resumo


def _resumo_clientes_duplicados() -> dict:
    df = calcular_clientes_duplicados()
    return {"disponivel": True, "total_registros_duplicados": len(df)}


def _resumo_divergencia_financeira() -> dict:
    df = calcular_divergencia_financeira()
    if df.empty:
        return {"disponivel": False}
    inconsistentes = df[df["inconsistente"]]
    resumo = {
        "disponivel": True,
        "total_meses_verificados": len(df),
        "total_meses_com_divergencia": len(inconsistentes),
    }
    if not inconsistentes.empty:
        pior = inconsistentes.sort_values("divergencia_abs", ascending=False).iloc[0]
        resumo["pior_empreendimento"] = pior["empreendimento"]
        resumo["pior_mes"] = pior["mes_referencia"]
        resumo["pior_divergencia_reais"] = pior["divergencia_abs"]
    return resumo


def _resumo_disponibilidade_unidades() -> dict:
    unidades = unidades_disponiveis()
    if not unidades:
        return {"disponivel": True, "total_unidades_disponiveis": 0}
    por_empreendimento = Counter(u["empreendimento_nome"] for u in unidades)
    return {
        "disponivel": True,
        "total_unidades_disponiveis": len(unidades),
        "top_empreendimentos_com_mais_disponibilidade": [
            {"empreendimento": nome, "unidades_disponiveis": qtd}
            for nome, qtd in por_empreendimento.most_common(3)
        ],
    }


def _resumo_qualidade_dado() -> dict:
    relatorio = relatorio_qualidade_dado()
    return {
        "disponivel": True,
        "campos_sem_preenchimento": sum(relatorio["nulos"].values()),
        "vendas_com_status_e_data_conflitantes_ja_corrigidas": relatorio[
            "conflitos_data_distrato_vs_status_venda"
        ]["total"],
        "meses_com_divergencia_financeira": relatorio["divergencias_financeiras"]["total_inconsistentes"],
        "total_registros_financeiros": relatorio["divergencias_financeiras"]["total_registros"],
    }


_CONSTRUTORES = {
    "velocidade_vendas": _resumo_velocidade_vendas,
    "estouro_custo": _resumo_estouro_custo,
    "clientes_duplicados": _resumo_clientes_duplicados,
    "divergencia_financeira": _resumo_divergencia_financeira,
    "qualidade_dado": _resumo_qualidade_dado,
    "disponibilidade_unidades": _resumo_disponibilidade_unidades,
}

_DOMINIOS_PADRAO = (
    "velocidade_vendas",
    "estouro_custo",
    "clientes_duplicados",
    "divergencia_financeira",
    "disponibilidade_unidades",
    "qualidade_dado",
)

_DOMINIOS_POR_PAGINA = {
    "Dashboard": _DOMINIOS_PADRAO,
    "Qualidade de Dados": ("qualidade_dado",),
    # qualidade_dado incluído aqui também: achado de auditoria (04/09/2026) — ao
    # perguntar "existem problemas de qualidade nos dados?" fora da página
    # Qualidade de Dados, o domínio não estava carregado e o LLM reaproveitava
    # métricas de outros domínios (estouro de custo, dispersão de velocidade de
    # vendas) como se fossem evidência de qualidade de dado, inclusive
    # inventando uma causa ("indica inconsistência na coleta") sem base nos
    # dados. Carregar qualidade_dado em toda página fecha esse ponto cego sem
    # depender só da instrução de prompt para não conflacionar domínios.
    "Vendas e Distratos": ("velocidade_vendas", "clientes_duplicados", "disponibilidade_unidades", "qualidade_dado"),
}


def montar_contexto(pagina_atual: str | None) -> dict:
    """
    Monta um resumo estruturado (não os dados brutos) dos indicadores relevantes para a
    página atual, reutilizando exclusivamente as funções já existentes em analytics/ e
    core/ — nenhum cálculo de negócio é reproduzido aqui.

    O domínio enviado ao LLM é restrito conforme a página atual, para não expor dados
    desnecessários a cada pergunta.
    """
    dominios = _DOMINIOS_POR_PAGINA.get(pagina_atual, _DOMINIOS_PADRAO)
    contexto = {}
    for nome_dominio in dominios:
        try:
            contexto[nome_dominio] = _CONSTRUTORES[nome_dominio]()
        except Exception:
            contexto[nome_dominio] = {"disponivel": False}
    return contexto


def responder(pergunta: str, pagina_atual: str | None = None, historico: list[dict] | None = None) -> dict:
    """
    Responde uma pergunta de análise de negócio.

    Fluxo: pergunta -> monta contexto estruturado (analytics/core) -> LLM interpreta o
    contexto. Se o LLM sinalizar que a pergunta exige um dado bruto fora desse contexto
    (marcador CONSULTA_SQL), a pergunta é roteada para nl_assistant.text_to_sql.perguntar(),
    que gera e executa uma SQL real (só SELECT) contra o banco — a SQL e o resultado bruto
    são retornados para exibição, garantindo rastreabilidade também nesse caminho.

    Retorna: {"resposta_texto": str, "sql": str | None, "resultado": list[dict] | None}.
    sql/resultado só vêm preenchidos quando a resposta veio de uma consulta real ao banco.

    Levanta EnvironmentError se a chave da API não estiver configurada.
    """
    if not _GROQ_API_KEY:
        raise EnvironmentError(
            "GROQ_API_KEY não configurada. Defina a variável no arquivo .env para usar o assistente."
        )

    from groq import Groq

    contexto = montar_contexto(pagina_atual)

    mensagens = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                f"Página atual do usuário no painel: {pagina_atual or 'não informada'}.\n"
                f"Dados estruturados disponíveis para esta pergunta (JSON): "
                f"{json.dumps(contexto, ensure_ascii=False)}"
            ),
        },
    ]
    for item in (historico or [])[-6:]:
        mensagens.append({"role": item["role"], "content": item["content"]})
    mensagens.append({"role": "user", "content": pergunta})

    client = Groq(api_key=_GROQ_API_KEY)
    completion = client.chat.completions.create(
        model=_MODELO,
        messages=mensagens,
        temperature=0.2,
        max_tokens=700,
    )
    resposta = completion.choices[0].message.content.strip()

    if resposta.startswith(_MARCADOR_CONSULTA_SQL):
        pergunta_reformulada = resposta[len(_MARCADOR_CONSULTA_SQL):].strip() or pergunta
        from nl_assistant.text_to_sql import perguntar

        try:
            resultado_sql = perguntar(pergunta_reformulada)
        except Exception:
            return {
                "resposta_texto": "Não foi possível consultar essa informação no banco agora.",
                "sql": None,
                "resultado": None,
            }
        return {
            "resposta_texto": resultado_sql["resposta_texto"],
            "sql": resultado_sql["sql"],
            "resultado": resultado_sql["resultado"],
        }

    return {"resposta_texto": resposta, "sql": None, "resultado": None}
