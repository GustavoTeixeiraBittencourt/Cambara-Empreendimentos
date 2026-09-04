import json
import os

from analytics.clientes_duplicados import calcular as calcular_clientes_duplicados
from analytics.divergencia_financeira import calcular as calcular_divergencia_financeira
from analytics.estouro_custo import calcular as calcular_estouro_custo
from analytics.velocidade_vendas import calcular as calcular_velocidade_vendas
from core.validacoes import relatorio_qualidade_dado

_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
_MODELO = "openai/gpt-oss-20b"

PERGUNTAS_SUGERIDAS = [
    "Quais empreendimentos precisam de atenção?",
    "Como está a velocidade de vendas?",
    "Existem problemas de qualidade nos dados?",
    "Quais são os principais insights?",
]

_SYSTEM_PROMPT = """\
Você é o Assistente de Análise de Negócio do painel executivo da Cambará Empreendimentos.
Seu papel é ajudar a diretoria a interpretar os indicadores já calculados pelo sistema.

Regras importantes:
- Responda SOMENTE com base nos dados estruturados fornecidos a seguir. Nunca invente ou
  estime números que não estejam presentes nesses dados.
- Se a pergunta exigir um dado que não está disponível no contexto fornecido, diga
  claramente que essa informação não está disponível, em vez de supor um valor.
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
}

_DOMINIOS_PADRAO = ("velocidade_vendas", "estouro_custo", "clientes_duplicados", "divergencia_financeira")

_DOMINIOS_POR_PAGINA = {
    "Dashboard": _DOMINIOS_PADRAO,
    "Qualidade de Dados": ("qualidade_dado",),
    "Vendas e Distratos": ("velocidade_vendas", "clientes_duplicados"),
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


def responder(pergunta: str, pagina_atual: str | None = None, historico: list[dict] | None = None) -> str:
    """
    Responde uma pergunta de análise de negócio interpretando indicadores já calculados
    pela camada de analytics/core.

    Fluxo: pergunta -> monta contexto estruturado (analytics/core) -> LLM interpreta o
    contexto -> resposta em linguagem natural. O LLM nunca recebe SQL nem dados brutos,
    e nunca executa cálculo de negócio — apenas interpreta o resumo já calculado.

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
    return completion.choices[0].message.content.strip()
