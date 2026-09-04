# Exploração de Dados — cambara_teste_tecnico.db

**Objetivo:** entender a qualidade e a estrutura da base antes de definir qualquer regra de negócio, seguindo o princípio *dado original ≠ dado tratado ≠ métrica calculada*. As decisões de regra tomadas a partir destes achados ficam registradas separadamente em `docs/business_rule.md` — este documento contém apenas o que foi **observado nos dados**, não decisões.

**Base:** SQLite, 7 tabelas — `empreendimentos`, `unidades`, `clientes`, `vendas`, `obra_andamento`, `financeiro_mensal`, `usuarios`.
**Data da exploração:** 02/09/2026.

---

## 1. Volume geral

| Tabela | Registros |
|---|---|
| empreendimentos | 22 |
| unidades | 3.300 |
| clientes | 2.691 |
| vendas | 2.206 |
| obra_andamento | 562 |
| financeiro_mensal | 562 |
| usuarios | 5 |

---

## 2. Nulos — varredura em todas as colunas de todas as tabelas

Fora dos pontos abaixo, **nenhuma outra coluna de nenhuma tabela possui valor nulo**.

| Tabela | Coluna | Nulos | Observação |
|---|---|---|---|
| empreendimentos | observacoes | 20 de 22 | Só 2 empreendimentos (id 17 e 21) têm observação registrada |
| obra_andamento | observacoes | 537 de 562 | 16 registros: "Estouro pontual de custo — retrabalho / reorçamento de insumos"; 9 registros: "Reclassificação de medição de avanço físico após revisão de engenharia" |
| vendas | data_distrato | 2.056 de 2.206 | Esperado — só é preenchido quando há distrato. Ver seção 5 sobre uma inconsistência real encontrada aqui |

**Leitura de negócio:** os nulos em `observacoes` não são um problema de qualidade — é campo opcional, preenchido só quando há algo relevante a registrar. O nulo em `data_distrato` é estrutural (só existe quando há distrato).

---

## 3. Integridade referencial

Checadas as 5 relações de chave estrangeira existentes na base — **nenhum órfão encontrado em nenhuma delas**:

| Relação | Órfãos |
|---|---|
| unidades.empreendimento_id → empreendimentos.id | 0 |
| vendas.unidade_id → unidades.id | 0 |
| vendas.cliente_id → clientes.id | 0 |
| obra_andamento.empreendimento_id → empreendimentos.id | 0 |
| financeiro_mensal.empreendimento_id → empreendimentos.id | 0 |

**Verificação adicional:** nenhuma unidade possui mais de uma venda com `status_venda` "ativa" simultaneamente (0 casos) — ou seja, não há indício de dupla venda já registrada no histórico da base.

---

## 4. Inconsistência de grafia (normalização necessária)

Duas colunas de status têm o mesmo valor de negócio escrito de formas diferentes:

**`unidades.status`:**

| Valor | Registros |
|---|---|
| vendida / VENDIDA / Vendida | 713 / 687 / 684 |
| Disponível / disponivel / DISPONIVEL | 315 / 298 / 298 |
| Reservada / reservada | 104 / 79 |
| Distrato / Cancelado / distrato | 44 / 40 / 38 |

**`vendas.status_venda`:**

| Valor | Registros |
|---|---|
| ATIVA / Ativa / ativa | 716 / 697 / 671 |
| distrato / Distrato / Distratada | 46 / 41 / 35 |

**Leitura de negócio:** ambas as colunas precisam de normalização de texto (case/acentuação) antes de qualquer contagem — sem isso, qualquer métrica que agrupe por status estaria sub-contada em ~2/3 dos casos reais.

---

## 5. Achado crítico — "Distrato" vs. "Cancelado" em `unidades.status`

O enunciado/roadmap levantou a dúvida: `Cancelado` (40 registros) e `Distrato`/`distrato` (82 registros somados) em `unidades.status` são a mesma categoria de negócio ou duas categorias distintas? Investigação feita em 3 etapas:

**5.1 — Toda unidade Cancelado/Distrato/distrato tem venda associada?**

Sim, **100% dos casos nas três grafias** (40/40 Cancelado, 44/44 Distrato, 38/38 distrato) têm ao menos uma venda relacionada — nenhuma unidade "nasce" cancelada sem nunca ter sido vendida.

**5.2 — Existe correspondência 1:1 entre a grafia da unidade e a grafia do `status_venda`?**

Não. Cruzando as duas colunas, as variações de `vendas.status_venda` (`distrato`/`Distrato`/`Distratada`) se distribuem de forma quase uniforme entre as três variações de `unidades.status` (`Cancelado`/`Distrato`/`distrato`) — não existe um padrão do tipo "toda venda Distratada vira unidade Cancelado".

**5.3 — Existe alguma variável de negócio (tempo até o distrato, valor da venda, forma de pagamento) que separe Cancelado de Distrato?**

Não foi encontrada nenhuma:

| Métrica | Cancelado | Distrato | distrato |
|---|---|---|---|
| Dias médios venda → distrato | ~178 | ~154 | ~182 |
| Valor médio da venda | R$ 2.353.806 | R$ 2.320.188 | R$ 2.114.374 |
| % Financiamento | ~48% | ~66% | ~79% |

As faixas se sobrepõem entre os três grupos, sem separação estatística clara.

**Conclusão (fato observado, não decisão):** os dados não fornecem nenhuma evidência de que `Cancelado` seja uma categoria de negócio diferente de `Distrato`/`distrato`. O padrão é consistente com o mesmo problema da seção 4 — três grafias do mesmo conceito. **A decisão formal de normalização (tratar como uma única categoria ou não) fica registrada em `docs/business_rule.md`.**

**5.4 — Inconsistência real encontrada (não é só grafia):**

37 registros em `vendas` têm `data_distrato` preenchida, mas `status_venda` ainda consta como "ativa" (em alguma grafia: 8 `ATIVA`, 17 `Ativa`, 12 `ativa`). Isso é uma contradição entre dois campos da mesma linha, não uma variação de texto — indica que o campo `status_venda` não é 100% confiável isoladamente para determinar se uma venda está ativa. Essa é uma decisão de negócio em aberto: qual campo tratar como fonte de verdade (`data_distrato IS NOT NULL` vs. o texto de `status_venda`) — a ser registrada em `docs/business_rule.md`.

---

## 6. Duplicidade de clientes

- 2.691 clientes, sendo 2.572 nomes distintos → **115 grupos de nome repetido, somando 234 linhas**.
- Ao inspecionar os grupos, a esmagadora maioria tem `cidade`, `email` e `data_cadastro` **todos diferentes** entre si — indicando homônimos (pessoas diferentes que compartilham nome), não duplicidade de cadastro.
- Achado estrutural relevante: o campo `email` é sintético e embute o próprio `id` do cliente (ex.: `debora.rodrigues.nascimento746@exemplo.com`). Por construção, **nunca se repete entre registros diferentes** — não serve como chave de deduplicação.
- Não existe CPF nem telefone na base.
- Aplicando um critério conservador (nome + cidade + data_cadastro **todos** iguais): **0 grupos encontrados**. O único caso que parecia promissor sob um critério mais frouxo (mesmo nome + mesma data de cadastro) — "Débora Rodrigues Nascimento", 28/02/2023 — tem cidades diferentes (Curitiba/PR e Marituba/PA), confirmando serem duas pessoas reais.

**Conclusão (fato observado):** sob um critério que minimiza falso positivo, esta base **não apresenta evidência de clientes duplicados**. A ausência de CPF/telefone limita qualquer deduplicação mais agressiva a um exercício de probabilidade, não de certeza. **O critério final adotado para a pergunta de negócio 3 fica registrado em `docs/business_rule.md`.**

---

## 7. `obra_andamento`

- `percentual_conclusao`: variação de **0,61 a 96,93** — nenhum registro fora da faixa 0–100.
- Observações (ver seção 2): 25 registros com observação relevante, divididos em dois padrões (estouro de custo pontual; reclassificação de medição de avanço físico), o restante nulo.

---

## 8. `financeiro_mensal` — divergência entre resultado reportado e recalculado

Recalculando `resultado_reportado` como `receita_reconhecida − custo_incorrido − despesas_corporativas_rat`:

- **63 de 562 registros (11,2%)** têm divergência absoluta maior que R$ 1 em relação ao valor reportado.
- A diferença varia de **−R$ 2.260.920,59 a +R$ 565.828,73**, com média de −R$ 2.681,57 — ou seja, quando diverge, tende a haver mais casos de resultado reportado subestimado do que superestimado, mas com dispersão grande (não é um viés pequeno e sistemático).

**Conclusão (fato observado):** a divergência é real e material em alguns casos (chega a milhões em módulo), não é um problema de arredondamento. **A tolerância a ser considerada "inconsistência real" para fins de reporte (pergunta de negócio 4) fica registrada em `docs/business_rule.md`.**

---

## 9. Resumo — o que ainda precisa virar regra de negócio (Bloco 2)

| # | Ponto em aberto | Onde será registrado |
|---|---|---|
| 1 | Normalização de status (`unidades.status`, `vendas.status_venda`) | `docs/business_rule.md` |
| 2 | Cancelado = Distrato? (evidência aponta que sim — decisão formal pendente) | `docs/business_rule.md` |
| 3 | Fonte de verdade quando `status_venda` e `data_distrato` divergem (37 casos) | `docs/business_rule.md` |
| 4 | Definição de "venda ativa" | `docs/business_rule.md` |
| 5 | Definição do denominador "total ofertado" (velocidade de vendas) | `docs/business_rule.md` |
| 6 | Critério final de cliente duplicado (evidência: 0 grupos sob critério conservador) | `docs/business_rule.md` |
| 7 | Tolerância de divergência financeira considerada "inconsistência real" | `docs/business_rule.md` |
| 8 | Tratamento da senha placeholder (`trocar_no_setup`) | `docs/business_rule.md` |
