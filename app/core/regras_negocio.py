from __future__ import annotations

import unicodedata
from datetime import date

from core.db import run_query, transaction
from core.exceptions import (
    ClienteInvalidoError,
    EmailJaCadastradoError,
    UnidadeIndisponivelError,
    UnidadeNaoEncontradaError,
    VendaJaDistratadaError,
    VendaNaoEncontradaError,
)

# Grafias/categorias reconhecidas (após normalizar_status) como "venda distratada"
# (regras 2+3, vendas.status_venda). Usado só para RECONHECER o dado bruto — o
# rótulo de negócio de SAÍDA é "distratada" (ver status_venda_normalizado(),
# revisado em 03/09/2026; ver docs/business_rule.md, regra 3, nota de revisão).
_CATEGORIAS_VENDA_DISTRATO = {"distrato", "distratada", "cancelado"}

# Grafias/categorias reconhecidas (após normalizar_status) como "unidade em
# distrato" (regra 2, unidades.status). Coluna diferente de status_venda, com
# decisão de nomenclatura própria: aqui o rótulo canônico continua "distrato"
# (não "distratada") — não houve pedido de mudança e os dados brutos desta
# coluna nunca usam a grafia "Distratada".
_CATEGORIAS_UNIDADE_DISTRATO = {"distrato", "cancelado"}


def normalizar_status(status: str) -> str:
    """
    Regra 1: minúsculo, sem acentos, sem espaços nas pontas.
    Ex: "VENDIDA" → "vendida", "Disponível" → "disponivel"
    """
    sem_acento = unicodedata.normalize("NFD", status)
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return sem_acento.lower().strip()


def esta_distratada(status_venda: str, data_distrato: str | None) -> bool:
    """
    Regras 2+3:
    - normalizar_status(status_venda) ∈ {"distrato","distratada","cancelado"}, OU
    - data_distrato preenchida (não None, não vazio).

    Trata "Distratada" como distrato (regra 3 — não resolvido só por normalização de grafia).
    """
    if data_distrato is not None and str(data_distrato).strip() != "":
        return True
    return normalizar_status(status_venda) in _CATEGORIAS_VENDA_DISTRATO


def esta_ativa(status_venda: str, data_distrato: str | None) -> bool:
    """Regra 4: not esta_distratada(...)."""
    return not esta_distratada(status_venda, data_distrato)


def status_venda_normalizado(status_venda: str, data_distrato: str | None = None) -> str:
    """
    Regras 1+3, como rótulo de texto (não booleano): devolve a categoria de
    negócio final de uma venda — "ativa" ou "distratada" — reaproveitando
    esta_distratada() para não duplicar a regra de decisão em dois lugares.

    Revisão de 03/09/2026 (docs/business_rule.md, regra 3): o rótulo canônico da
    categoria de distrato em vendas.status_venda passou de "distrato" para
    "distratada" — par gramatical de "ativa" (ambos adjetivos; "distrato" é
    substantivo). Não muda o reconhecimento do dado bruto, só o valor final
    exibido/gravado. Espelhado em sql/views.sql (vw_vendas.status_venda_normalizado).

    Com data_distrato=None (padrão), colapsa só a grafia/categoria textual — útil
    para reportar quais categorias de negócio existem a partir de valores
    distintos de status_venda, sem precisar de uma linha real com data_distrato
    preenchida (ex.: painel de Qualidade de Dados).
    """
    return "distratada" if esta_distratada(status_venda, data_distrato) else "ativa"


def categoria_status_unidade(status: str) -> str:
    """
    Regras 1+2 (unidades.status), como rótulo de texto: normaliza grafia e funde
    "distrato"/"cancelado" na categoria canônica "distrato" — mesma unificação já
    usada em regras_negocio para a coluna de unidades (regra 2), aqui exposta
    como função reutilizável em vez de repetida inline em cada tela/consulta.
    Espelhado em sql/views.sql (vw_unidades.status_categoria).
    """
    normalizado = normalizar_status(status)
    return "distrato" if normalizado in _CATEGORIAS_UNIDADE_DISTRATO else normalizado


def registrar_venda(
    unidade_id: int,
    cliente_id: int | None,
    cliente_novo: dict | None,
    data_venda: str,
    valor_venda: float,
    forma_pagamento: str,
) -> dict:
    """
    Registra uma nova venda de forma atômica (BEGIN/COMMIT/ROLLBACK).

    - Valida que a unidade existe (senão UnidadeNaoEncontradaError) e que seu
      status normalizado é "disponivel" (senão UnidadeIndisponivelError).
    - Valida valor_venda > 0 (senão ValueError).
    - Se cliente_novo vier preenchido ({nome, cidade, uf, perfil, email}), valida
      que o e-mail (se informado) não pertence a nenhum cliente já cadastrado
      (senão EmailJaCadastradoError) e insere em clientes. Senão, valida que
      cliente_id foi informado e corresponde a um cliente existente (senão
      ClienteInvalidoError) — o backend não confia que quem chamou esta
      função já filtrou um cliente válido (ex.: uma tela).
    - Insere em vendas.
    - Atualiza unidades.status = "vendida".
    - Retorna {venda_id, unidade_id, cliente_id}.
    """
    if valor_venda is None or valor_venda <= 0:
        raise ValueError("valor_venda deve ser maior que zero.")

    with transaction() as cur:
        # 1. Verificar existência e disponibilidade da unidade
        row = cur.execute(
            "SELECT status FROM unidades WHERE id = ?", (unidade_id,)
        ).fetchone()
        if row is None:
            raise UnidadeNaoEncontradaError(f"Unidade {unidade_id} não encontrada.")
        if normalizar_status(row["status"]) != "disponivel":
            raise UnidadeIndisponivelError(
                f"Unidade {unidade_id} não está disponível (status atual: '{row['status']}')."
            )

        # 2. Inserir cliente novo, ou validar que o cliente_id informado existe
        if cliente_novo is not None:
            email_novo = (cliente_novo.get("email") or "").strip()
            if email_novo:
                cliente_com_mesmo_email = cur.execute(
                    "SELECT id FROM clientes WHERE email = ?", (email_novo,)
                ).fetchone()
                if cliente_com_mesmo_email is not None:
                    raise EmailJaCadastradoError(
                        f"O e-mail '{email_novo}' já está cadastrado para outro cliente."
                    )

            data_cadastro = cliente_novo.get("data_cadastro", date.today().isoformat())
            cur.execute(
                "INSERT INTO clientes (nome, cidade, uf, perfil, data_cadastro, email) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    cliente_novo["nome"],
                    cliente_novo["cidade"],
                    cliente_novo["uf"],
                    cliente_novo["perfil"],
                    data_cadastro,
                    cliente_novo["email"],
                ),
            )
            cliente_id = cur.lastrowid
        else:
            if cliente_id is None:
                raise ClienteInvalidoError(
                    "Informe um cliente existente (cliente_id) ou os dados de um novo cliente (cliente_novo)."
                )
            cliente_row = cur.execute(
                "SELECT id FROM clientes WHERE id = ?", (cliente_id,)
            ).fetchone()
            if cliente_row is None:
                raise ClienteInvalidoError(f"Cliente {cliente_id} não encontrado.")

        # 3. Inserir venda
        cur.execute(
            """
            INSERT INTO vendas (unidade_id, cliente_id, data_venda, valor_venda,
                                forma_pagamento, status_venda)
            VALUES (?, ?, ?, ?, ?, 'ativa')
            """,
            (unidade_id, cliente_id, data_venda, valor_venda, forma_pagamento),
        )
        venda_id = cur.lastrowid

        # 4. Atualizar status da unidade
        cur.execute(
            "UPDATE unidades SET status = 'vendida' WHERE id = ?", (unidade_id,)
        )

    return {"venda_id": venda_id, "unidade_id": unidade_id, "cliente_id": cliente_id}


def registrar_distrato(venda_id: int, data_distrato: str) -> dict:
    """
    Registra um distrato de forma atômica (BEGIN/COMMIT/ROLLBACK).

    - Busca a venda (senão VendaNaoEncontradaError).
    - Valida esta_ativa() (senão VendaJaDistratadaError).
    - Atualiza vendas.status_venda = "distratada" + data_distrato (revisado em
      03/09/2026 — canônico era "distrato", ver regra 3).
    - Atualiza unidades.status = "distrato" (regra 9 — NÃO "disponivel";
      unidades.status é coluna à parte, sem essa revisão de nomenclatura).
    - Retorna {venda_id, unidade_id, novo_status_unidade}.
    """
    with transaction() as cur:
        row = cur.execute(
            "SELECT id, unidade_id, status_venda, data_distrato FROM vendas WHERE id = ?",
            (venda_id,),
        ).fetchone()
        if row is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")

        if not esta_ativa(row["status_venda"], row["data_distrato"]):
            raise VendaJaDistratadaError(
                f"Venda {venda_id} já está distratada."
            )

        unidade_id = row["unidade_id"]

        # Atualizar vendas
        cur.execute(
            "UPDATE vendas SET status_venda = 'distratada', data_distrato = ? WHERE id = ?",
            (data_distrato, venda_id),
        )

        # Atualizar unidades: "distrato", NÃO "disponivel" (regra 9)
        cur.execute(
            "UPDATE unidades SET status = 'distrato' WHERE id = ?", (unidade_id,)
        )

    return {"venda_id": venda_id, "unidade_id": unidade_id, "novo_status_unidade": "distrato"}


def unidades_disponiveis(empreendimento_id: int | None = None) -> list[dict]:
    """
    Lista unidades com status normalizado == "disponivel".
    Se empreendimento_id for passado, filtra por empreendimento.
    """
    if empreendimento_id is not None:
        rows = run_query(
            """
            SELECT u.id, u.empreendimento_id, u.identificador, u.tipo,
                   u.area_privativa_m2, u.valor_tabela, u.status,
                   e.nome AS empreendimento_nome
            FROM unidades u
            JOIN empreendimentos e ON e.id = u.empreendimento_id
            WHERE u.empreendimento_id = ?
            """,
            (empreendimento_id,),
        )
    else:
        rows = run_query(
            """
            SELECT u.id, u.empreendimento_id, u.identificador, u.tipo,
                   u.area_privativa_m2, u.valor_tabela, u.status,
                   e.nome AS empreendimento_nome
            FROM unidades u
            JOIN empreendimentos e ON e.id = u.empreendimento_id
            """
        )
    return [r for r in rows if normalizar_status(r["status"]) == "disponivel"]
