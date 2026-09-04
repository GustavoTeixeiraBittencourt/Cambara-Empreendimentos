# Contrato de Interface — Núcleo (Dados/Regras) x Interface (Streamlit)

Este documento existe para permitir que dois agentes trabalhem em paralelo sem se bloquear: quem escreve as páginas Streamlit não precisa esperar o núcleo estar pronto, porque já sabe o nome, a assinatura e o formato de retorno de cada função. Gerado em 03/09/2026, a partir do schema real do banco (`data/cambara_teste_tecnico.db`) e de `docs/business_rule.md` (9 regras já fechadas — este documento não reabre nenhuma delas, só define como elas viram funções Python).

**Regra geral do contrato:** o núcleo nunca retorna cursor de banco nem SQL cru para a interface — sempre `pandas.DataFrame`, `dict` ou `list[dict]`, e erros de regra de negócio são exceções nomeadas (não strings soltas), para a interface poder tratar cada caso com uma mensagem clara ao usuário.

---

## ⚠️ Achado de validação que os 9 regras não cobrem explicitamente

Conferido agora no banco (`SELECT DISTINCT`):

- `unidades.status`: `vendida, VENDIDA, Vendida, disponivel, Disponível, DISPONIVEL, reservada, Reservada, distrato, Distrato, Cancelado` → normalizado (regra 1, sem acento/minúsculo) vira exatamente: `vendida, disponivel, reservada, distrato, cancelado`. **A categoria "disponível" depois de normalizada é `disponivel` sem acento** — o exemplo com acento em `business_rule.md` (regra 2) é só prosa, não o valor literal. Todo filtro de disponibilidade em `core/regras_negocio.py` deve comparar contra `"disponivel"` sem acento.
- `vendas.status_venda`: `Ativa, ativa, ATIVA, Distrato, distrato, Distratada`. **Existe uma 4ª grafia, `"Distratada"`, que a regra 1 (normalização de acento/caixa) sozinha NÃO resolve** — `normalizar_status("Distratada")` vira `"distratada"`, que é uma string diferente de `"distrato"`. Ou seja, `esta_distratada()` precisa de um mapa de categoria (não só normalização de grafia) que trate `{"distrato", "distratada", "cancelado"}` como a mesma categoria de negócio, igual já foi feito para `unidades.status` na regra 2. Sem isso, uma venda com `status_venda = "Distratada"` e `data_distrato = NULL` seria contada erroneamente como ativa.

Isso é exatamente o tipo de caso de borda que a apresentação vai valorizar se vocês (o Agente Dados & Regras) conseguirem mostrar que pegaram — e vai doer se passar batido, porque afeta a Pergunta de Negócio 1 e a validação de "unidade disponível" na camada de escrita.

---

## Schema real (referência rápida)

```
empreendimentos(id, nome, cidade, uf, tipo, modelo_negocio, vgv_estimado, data_lancamento, status, observacoes)  -- 22 linhas
unidades(id, empreendimento_id, identificador, tipo, area_privativa_m2, valor_tabela, status)                    -- 3300 linhas
clientes(id, nome, cidade, uf, perfil, data_cadastro, email)                                                     -- 2691 linhas
vendas(id, unidade_id, cliente_id, data_venda, valor_venda, forma_pagamento, status_venda, data_distrato)         -- 2206 linhas
obra_andamento(id, empreendimento_id, mes_referencia, percentual_conclusao, custo_orcado_mes, custo_realizado_mes, observacoes) -- 562 linhas
financeiro_mensal(id, empreendimento_id, mes_referencia, receita_reconhecida, custo_incorrido, despesas_corporativas_rat, resultado_reportado) -- 562 linhas
usuarios(id, nome, email, papel, senha_hash)                                                                     -- 5 linhas
```

---

## `core/db.py`

- `get_connection() -> sqlite3.Connection` — abre conexão com `row_factory=sqlite3.Row`, caminho do banco vindo de config/env, não hardcoded espalhado pelo código. **Revisado em 04/09/2026:** executa `PRAGMA foreign_keys = ON` em toda conexão — o SQLite não aplica as cláusulas `REFERENCES` do schema sem esse pragma (por conexão), então antes desta correção um `cliente_id`/`unidade_id` inexistente era aceito silenciosamente em qualquer `INSERT`. É defesa em profundidade, além da validação explícita já feita em `registrar_venda`.
- `caminho_banco() -> str` — **novo em 04/09/2026** — expõe o caminho do arquivo de banco em uso (o mesmo valor interno usado por `get_connection()`, incluindo quando sobrescrito por `DB_PATH`). Usado pela página Assistente para mostrar o nome do banco consultado no log de auditoria de cada resposta.
- `run_query(sql: str, params: tuple = ()) -> list[dict]` — só leitura, usado por analytics e pelo assistente de NL.
- `transaction() -> contextmanager` — abre `BEGIN`, expõe um cursor, faz `COMMIT` no sucesso e `ROLLBACK` em qualquer exceção. É isso que garante atomicidade em `registrar_venda`/`registrar_distrato` (alterar `vendas` E `unidades` juntas, ou nenhuma).

## `core/exceptions.py`

- `UnidadeIndisponivelError(Exception)` — unidade **existe**, mas não está com status normalizado `"disponivel"`.
- `UnidadeNaoEncontradaError(Exception)` — **novo em 04/09/2026** — `unidade_id` não corresponde a nenhuma unidade cadastrada. Separado de `UnidadeIndisponivelError` porque são causas diferentes (dado inválido vs. regra de negócio) e a tela deve poder tratar cada uma com uma mensagem própria.
- `ClienteInvalidoError(Exception)` — **novo em 04/09/2026** — `cliente_id` informado não corresponde a nenhum cliente cadastrado, ou nem `cliente_id` nem `cliente_novo` foram informados. Fecha um gap encontrado em revisão: antes desta correção, `registrar_venda` aceitava um `cliente_id` inexistente e gravava a venda mesmo assim, porque a validação existia só na tela (dropdown), não no núcleo.
- `EmailJaCadastradoError(Exception)` — **novo em 04/09/2026** — o e-mail de um `cliente_novo` já pertence a outro cliente cadastrado. Verificado no backend (`registrar_venda`), não só no formulário — mesmo padrão de defesa em profundidade de `ClienteInvalidoError`.
- `VendaNaoEncontradaError(Exception)`
- `VendaJaDistratadaError(Exception)` — venda já está `esta_distratada() == True`.

## `core/regras_negocio.py`

- `normalizar_status(status: str) -> str` — regra 1 (minúsculo, sem acento, sem espaço nas pontas).
- `esta_distratada(status_venda: str, data_distrato: str | None) -> bool` — regras 2+3: categoria normalizada em `{"distrato","distratada","cancelado"}` OU `data_distrato` preenchida.
- `esta_ativa(status_venda: str, data_distrato: str | None) -> bool` — regra 4: `not esta_distratada(...)`.
- `registrar_venda(unidade_id: int, cliente_id: int | None, cliente_novo: dict | None, data_venda: str, valor_venda: float, forma_pagamento: str) -> dict` — dentro de `transaction()`: valida `valor_venda > 0` (senão `ValueError`); valida que a unidade existe (senão `UnidadeNaoEncontradaError`) e que `unidades.status` normalizado == `"disponivel"` (senão `UnidadeIndisponivelError`); se `cliente_novo` vier preenchido (`{nome, cidade, uf, perfil, email}`), valida que o e-mail (se não vazio) não pertence a nenhum cliente já cadastrado (senão `EmailJaCadastradoError`, novo em 04/09/2026) e insere em `clientes`; **senão, valida que `cliente_id` foi informado e corresponde a um cliente existente (senão `ClienteInvalidoError`)** — revisado em 04/09/2026, ver nota em `core/exceptions.py`; insere em `vendas`; atualiza `unidades.status = "vendida"`. Retorna `{venda_id, unidade_id, cliente_id}`.
- `registrar_distrato(venda_id: int, data_distrato: str) -> dict` — dentro de `transaction()`: busca a venda (senão `VendaNaoEncontradaError`); valida `esta_ativa()` (senão `VendaJaDistratadaError`); atualiza `vendas.status_venda = "distratada"` (rótulo revisado em 03/09/2026, ver `docs/business_rule.md` regra 3 — era `"distrato"`) + `data_distrato`; atualiza `unidades.status = "distrato"` (regra 9 — **não** `"disponivel"`; coluna de unidades não afetada pela revisão). Retorna `{venda_id, unidade_id, novo_status_unidade}`.
- `unidades_disponiveis(empreendimento_id: int | None = None) -> list[dict]` — lista para popular o formulário de venda (status normalizado `"disponivel"`).

## `core/auth.py`

- `autenticar(email: str, senha: str) -> dict | None` — `sha256(senha).hexdigest() == usuarios.senha_hash`; retorna `{id, nome, email, papel}` ou `None`.

## `core/validacoes.py`

- `integridade_referencial() -> list[dict]` — **novo em 04/09/2026** — `[{relacao, registros_sem_correspondencia}, ...]`, uma linha por FK do schema (5 relações), com contagem real via `LEFT JOIN` — substitui a lista fixa `[0, 0, 0, 0, 0]` que a tela de Qualidade de Dados exibia antes (gap encontrado em revisão: a tela afirmava uma verificação que não existia em código).
- `unidades_com_dupla_venda_ativa() -> list[dict]` — **novo em 04/09/2026** — `[{unidade_id, vendas_ativas_ids}, ...]`, vazio no caminho esperado; verificação viva de que nenhuma unidade tem mais de uma venda `esta_ativa()` simultânea (regra 4), no lugar de uma afirmação de texto sem consulta por trás.
- `relatorio_qualidade_dado() -> dict` — os achados já fechados de `docs/data_exploration.md` (nulos, grafias, os 37 casos de conflito da regra 3, os 63 casos de divergência financeira da regra 7) num formato estruturado, para a página de dashboard exibir sem reprocessar tudo na tela. Inclui também `integridade_referencial` e `unidades_com_dupla_venda_ativa` (acima).

## `analytics/velocidade_vendas.py`

- `calcular() -> pandas.DataFrame` — colunas: `empreendimento, total_ofertado, vendas_liquidas, velocidade_pct`. Aplica regra 5 (denominador = todas as unidades, sem filtrar por status do empreendimento) e regras 1–4 (vendas líquidas = ativas).

## `analytics/estouro_custo.py`

- `calcular() -> pandas.DataFrame` — colunas: `empreendimento, custo_orcado_acumulado, custo_realizado_acumulado, estouro_absoluto, estouro_pct`, a partir de `obra_andamento`.

## `analytics/clientes_duplicados.py`

- `calcular() -> pandas.DataFrame` — regra 6 (nome+cidade+data_cadastro idênticos). Nesta base, resultado esperado é vazio — a função deve retornar um DataFrame vazio com as colunas certas, não `None` nem erro, e a página precisa saber exibir "nenhum duplicado sob este critério" como resultado válido, não como bug.

## `analytics/divergencia_financeira.py`

- `calcular() -> pandas.DataFrame` — colunas: `empreendimento, mes_referencia, resultado_reportado, resultado_recalculado, divergencia_abs, inconsistente`. Regra 7 (tolerância R$1,00).

## `nl_assistant/guardrails.py`

- `validar_apenas_select(sql: str) -> None` — levanta `ValueError` se a query gerada não começar com `SELECT` (case-insensitive, ignorando espaços/comentários) ou contiver `;` seguido de outro comando. Chamada **antes** de qualquer execução.

## `nl_assistant/text_to_sql.py`

- `perguntar(pergunta: str) -> dict` — `{sql: str, resultado: list[dict], resposta_texto: str}`. Monta prompt com o schema acima + a pergunta, chama Groq, valida com `validar_apenas_select`, executa com `run_query`, gera uma resposta curta em português a partir do resultado. A página exibe `sql` e `resultado` sempre — é isso que torna a resposta rastreável.

---

## Divisão de arquivos entre os dois agentes (sem sobreposição)

**Agente "Dados & Regras"** possui: `app/core/*.py`, `app/analytics/*.py`, `app/nl_assistant/*.py`, `scripts/setup_senhas.py`, `tests/test_regras_negocio.py`.

**Agente "Interface"** possui: `app/main.py`, `app/pages/*.py`.

Nenhum dos dois deve editar arquivo do outro. Se um precisar de uma função que não está neste contrato, ele para e propõe a assinatura aqui antes de implementar — não decide sozinho um contrato novo.
