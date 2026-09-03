# Regras de Negócio — Cambará Empreendimentos S.A

Este documento registra as decisões formais de negócio tomadas a partir dos achados de `docs/data_exploration.md`. Cada regra segue o formato: Problema → Regra → Fórmula → Exemplo → Impacto → Implementação → Validação.

**Status:** Confirmada — todas as 9 regras abaixo estão fechadas para o projeto. Onde a decisão nasceu de uma leitura dos dados (não de uma restrição literal do enunciado), isso está explícito no campo "Regra".

---

### 1. Normalização de Status

**Status:**  Confirmada

**Problema:** as colunas `unidades.status` e `vendas.status_venda` registram o mesmo conceito de negócio com grafias diferentes (ex: `VENDIDA`, `Vendida`, `vendida`). Qualquer contagem direta sobre essas colunas sub-conta o resultado real, porque o banco trata cada grafia como um valor distinto.

**Regra:** todo valor de status é normalizado para minúsculo, sem acentos e sem espaços nas extremidades, antes de qualquer comparação, filtro ou agregação. A normalização acontece numa função central, nunca repetida em cada tela ou consulta separadamente.

**Fórmula:** `status_normalizado = strip(lower(remover_acentos(status_original)))`

**Exemplo:** `"VENDIDA"`, `"Vendida"` e `"vendida"` → todos viram `"vendida"`. Em `unidades.status`, os três valores somam 713 + 687 + 684 = **2.084 unidades vendidas** (e não 3 grupos separados).

**Impacto:** Pergunta de Negócio 1 (velocidade de vendas), tela de Vendas e Distratos (validação de disponibilidade), qualquer dashboard agrupado por status.

**Implementação:** `core/regras_negocio.py`, função `normalizar_status()`, aplicada na camada de acesso a dados (`core/db.py`) assim que o resultado sai do banco.

**Validação:** `select distinct status from unidades` retorna 11 grafias distintas antes da normalização; após aplicar a regra, cai para 5 valores de grafia única (conferido em banco). Combinada com a regra 2, cai para as 4 categorias de negócio finais.

---

### 2. Unificação "Cancelado" e "Distrato"

**Status:**  Confirmada — decisão baseada em evidência dos dados (nenhuma variável testada separa as categorias); tratada como conclusão de análise, não como fato absoluto do negócio, caso surja informação nova.

**Problema:** além da grafia inconsistente (regra 1), `unidades.status` tem três valores que poderiam representar 2 conceitos de negócio diferentes ou 1 só: `Cancelado` (40), `Distrato` (44), `distrato` (38).

**Regra:** tratar `Cancelado`, `Distrato` e `distrato` como a mesma categoria de negócio após normalização (`distrato`), porque nenhuma variável testada separa os grupos:

- 100% das unidades nas três grafias têm venda associada (nenhuma nasce cancelada sem nunca ter sido vendida);
- não há correspondência 1:1 entre a grafia de `unidades.status` e a de `vendas.status_venda` (as variações se misturam quase uniformemente);
- tempo médio até o distrato (144–213 dias), valor médio da venda (R$ 2,1M–2,35M) e forma de pagamento (~48–79% financiamento) não mostram separação clara entre os três grupos.

**Fórmula:** não aplicável (regra de categorização, não de cálculo).

**Exemplo:** uma unidade com status `"Cancelado"` e outra com `"Distrato"` são tratadas de forma idêntica em qualquer métrica — ambas contam como "unidade distratada".

**Impacto:** Pergunta de Negócio 1 (vendas líquidas = vendas brutas − distratos), regra de "unidade disponível para venda" (regra 4), tela de Vendas e Distratos.

**Implementação:** `core/regras_negocio.py`, mapa de normalização de categoria (`Cancelado` e `Distrato` → `distrato`), aplicado após a normalização de grafia da regra 1.

**Validação:** após as regras 1 e 2, `unidades.status` tem exatamente 4 categorias de negócio (`vendida`, `disponível`, `reservada`, `distrato`) — conferido em banco, contra as 11 grafias originais.

---

### 3. Fonte de Verdade em Conflito (status_venda × data_distrato)

**Status:** Confirmada

**Problema:** 37 registros em `vendas` têm `data_distrato` preenchida, mas `status_venda` ainda consta como "ativa" (alguma grafia). Os dois campos discordam sobre o mesmo fato.

**Regra:** `data_distrato` tem precedência sobre `status_venda`. Se `data_distrato` estiver preenchida, a venda é tratada como distratada, independentemente do texto em `status_venda`. Justificativa: a data é um evento factual (aconteceu ou não), enquanto o texto do status está sujeito a erro de digitação/atualização manual — já demonstrado pela inconsistência de grafia da regra 1.

**Fórmula:** `venda_distratada = (status_venda_normalizado == "distrato") OR (data_distrato IS NOT NULL)`

**Exemplo:** uma venda com `status_venda = "Ativa"` e `data_distrato = "2024-03-15"` é tratada como distratada, mesmo o texto dizendo o contrário.

**Impacto:** define diretamente a regra 4 (venda ativa) e a Pergunta de Negócio 1 (vendas líquidas).

**Implementação:** `core/regras_negocio.py`, função `esta_distratada()`, usada por toda função que precisar classificar uma venda.

**Validação:** `select count(*) from vendas where data_distrato is not null and status_venda_normalizado != 'distrato'` retorna 37 — reportado à parte no painel de qualidade de dado como "37 casos corrigidos pela regra de precedência", evidenciando que a regra foi de fato aplicada, não apenas ignorada.

---

### 4. Definição de "Venda Ativa"

**Status:** Confirmada (decorre diretamente das regras 1 e 3)

**Problema:** várias métricas (velocidade de vendas, ticket médio, dashboard) precisam de uma definição única e auditável de "venda ativa" — sem isso, cada função poderia implementar sua própria lógica e gerar números divergentes entre telas.

**Regra:** uma venda é "ativa" quando, após normalização (regra 1) e aplicação da precedência de distrato (regra 3), **não** está classificada como distratada.

**Fórmula:** `venda_ativa = NOT esta_distratada(venda)`

**Exemplo:** uma venda com `status_venda = "ATIVA"` e `data_distrato = NULL` é ativa. Uma venda com `status_venda = "ativa"` mas `data_distrato = "2024-03-15"` **não** é ativa (regra 3).

**Impacto:** numerador/filtro de praticamente todas as métricas de vendas; regra de bloqueio de venda de unidade indisponível.

**Implementação:** `core/regras_negocio.py`, função `esta_ativa()`.

**Validação:** contagem de vendas ativas antes e depois da regra 3 difere em exatamente 37 (os casos de conflito corrigidos) — conferido em banco.

---

### 5. Definição de "Total Ofertado"

**Status:**  Confirmada

**Problema:** a Pergunta de Negócio 1 (velocidade de vendas) precisa de um denominador — "quantas unidades foram ofertadas ao mercado". Não estava claro se unidades de empreendimentos com obra suspensa (`status = "Suspenso"`, 98 unidades) devem entrar nessa contagem.

**Regra:** "total ofertado" = todas as unidades cadastradas em `unidades`, **independentemente do status atual do empreendimento** (`Em obras`, `Concluído`, `Suspenso` ou `Lançamento`). Justificativa: uma unidade que já foi cadastrada como produto comercial já foi "ofertada" ao mercado em algum momento — o status do empreendimento reflete o andamento da obra, não se a unidade deixou de ser um produto à venda. Excluir "Suspenso" infla artificialmente a métrica de velocidade de vendas dos empreendimentos parados (denominador menor, percentual maior), o que seria enganoso justamente nos casos que mais precisam de atenção.

**Fórmula:** `total_ofertado(empreendimento) = count(unidades WHERE empreendimento_id = X)`, sem filtro por status do empreendimento.

**Exemplo:** um empreendimento "Suspenso" com 20 unidades cadastradas conta como 20 unidades ofertadas no denominador, mesmo que a obra esteja parada.

**Impacto:** Pergunta de Negócio 1 (velocidade de vendas) — denominador direto.

**Implementação:** `analytics/velocidade_vendas.py`.

**Validação:** somar `total_ofertado` de todos os empreendimentos bate com `select count(*) from unidades` = 3.300 — conferido em banco.

---

### 6. Critério de Cliente Duplicado

**Status:** Confirmada

**Problema:** a Pergunta de Negócio 3 pede identificação de clientes duplicados. Não existe CPF nem telefone na base — apenas nome, cidade, perfil, e-mail e data de cadastro. O e-mail é sintético (embute o próprio `id` do cliente, ex: `nome.sobrenome746@exemplo.com`) e por isso nunca se repete entre registros — não serve como chave de deduplicação.

**Regra:** um cliente é considerado duplicado apenas quando `nome`, `cidade` e `data_cadastro` são **todos** idênticos entre dois ou mais registros (critério conservador, minimiza falso positivo). Aplicando este critério na base atual: **0 grupos encontrados**. Dos 115 grupos de nome repetido (234 linhas), a esmagadora maioria tem cidade, e-mail e data de cadastro diferentes entre si — são homônimos, não duplicidade de cadastro.

**Fórmula:** `duplicado = COUNT(*) OVER (PARTITION BY nome, cidade, data_cadastro) > 1`

**Exemplo:** "Débora Rodrigues Nascimento", cadastrada em 28/02/2023, aparece duas vezes — mas em Curitiba/PR e Marituba/PA, cidades diferentes. Sob este critério, **não** é duplicidade.

**Impacto:** Pergunta de Negócio 3 e qualquer métrica de "clientes únicos"/ticket médio por cliente.

**Implementação:** `analytics/clientes_duplicados.py`. O README documenta explicitamente a limitação: sem CPF/telefone, deduplicação mais agressiva seria probabilística, não determinística, e este teste optou pelo critério que não gera falso positivo.

**Validação:** resultado esperado = 0 grupos nesta base (conferido em banco); a validação real está em mostrar que o critério é reproduzível e defensável, não em "achar" duplicados artificialmente.

---

### 7. Tolerância de Divergência Financeira

**Status:** Confirmada

**Problema:** 63 dos 562 registros de `financeiro_mensal` têm `resultado_reportado` divergente do valor recalculado (`receita_reconhecida − custo_incorrido − despesas_corporativas_rat`). Sem uma tolerância definida, qualquer diferença de centavos (arredondamento de ponto flutuante) apareceria como "inconsistência", poluindo o relatório.

**Regra:** considerar inconsistência qualquer divergência **absoluta** maior que R$ 1,00 entre o resultado reportado e o recalculado. Abaixo disso, considerado igual (ruído de arredondamento de sistema).



**Fórmula:**
```
resultado_recalculado = receita_reconhecida − custo_incorrido − despesas_corporativas_rat
divergencia = abs(resultado_reportado − resultado_recalculado)
inconsistente = divergencia > 1.00
```


**Impacto:** painel de qualidade de dado financeiro; Pergunta de Negócio 4 (divergência financeira).

**Implementação:** `analytics/divergencia_financeira.py`.

**Validação:** 499 registros com divergência ≤ R$ 1,00 (ruído de ponto flutuante); 63 registros (11,2% da base) acima da tolerância, distribuídos em 18 empreendimentos distintos — cada linha de `financeiro_mensal` já é uma combinação única de empreendimento/mês, então os 63 registros correspondem a 63 combinações mês/empreendimento distintas. Nenhum registro cai entre R$ 1,00 e R$ 282,57 — confirma que o critério é robusto e não sensível ao valor exato do limiar dentro dessa faixa. Todos os números desta seção foram reconferidos diretamente em banco.

---

### 8. Tratamento da Senha Placeholder

**Status:**  Confirmada

**Problema:** a coluna `usuarios.senha_hash` está preenchida com o valor literal `'trocar_no_setup'` para os 5 usuários — não é um hash de verdade, é um placeholder aguardando decisão de setup.

**Regra:** gerar o hash SHA-256 de uma senha temporária padrão e documentada (ex: `cambara2026`), substituindo o placeholder nos 5 registros. O login compara o hash da senha digitada com o hash armazenado. O README documenta explicitamente que isso é uma simplificação adequada ao escopo do teste (o próprio enunciado permite "hash simples ou verificação direta, desde que documentado") e que uma versão de produção exigiria bcrypt/argon2 com salt e fluxo de troca obrigatória no primeiro acesso.

**Fórmula:** `senha_hash = sha256(senha_temporaria_documentada)`

**Exemplo:** os 5 usuários passam a logar com a senha `cambara2026` (ou outra definida), cujo hash SHA-256 substitui `'trocar_no_setup'` na base.

**Impacto:** `core/auth.py`, tela de login — bloqueia o acesso à aplicação até ser resolvido.

**Implementação:** script de setup único (`scripts/setup_senhas.py` ou similar) rodado uma vez para popular os hashes; `core/auth.py` faz a comparação de hash no login.

**Validação:** login manual com a senha documentada autentica com sucesso nos 5 usuários; tentativa com senha errada falha. `select count(*) from usuarios where senha_hash='trocar_no_setup'` = 5 antes do setup — conferido em banco.

---

### 9. Comportamento da Unidade Após o Distrato

**Status:** Confirmada

**Problema:** ao registrar um distrato na camada de escrita, a unidade precisa assumir um novo status em `unidades.status`. O enunciado não define esse comportamento explicitamente, e é uma decisão que afeta diretamente a camada de escrita — o componente mais observado da avaliação.

**Regra:** ao registrar um distrato, a unidade muda de `vendida` para `distrato` (categoria já unificada pela regra 2) — **não** retorna automaticamente para `disponível`. A liberação da unidade para nova venda é uma ação manual separada, fora do fluxo automático de distrato. Justificativa de negócio: um distrato normalmente envolve verificação contratual e financeira antes de a unidade voltar ao estoque comercial — automatizar essa liberação poderia recolocar à venda uma unidade com pendência ainda não resolvida.

**Exemplo:** unidade 1234 com `status = vendida` sofre um distrato → status vira `distrato`. Ela só volta a aparecer na lista de unidades vendáveis se alguém, manualmente, alterar seu status para `disponível`.

**Impacto:**
- Fluxo "Registrar venda": unidades em `distrato` não entram na lista de unidades vendáveis até liberação manual.
- Fluxo "Registrar distrato": a transação grava `status_venda = 'distrato'` em `vendas` (com `data_distrato`) e `status = 'distrato'` em `unidades` — não `'disponível'` — na mesma transação atômica (BEGIN/COMMIT único).
- Pergunta de Negócio 1 (velocidade de vendas): unidades em `distrato` não contam como disponíveis no momento da consulta.

**Implementação:** dentro da transação de `core/regras_negocio.py` que processa o distrato.

**Validação:** esta é uma decisão de design, não uma regra extraída estatisticamente dos dados — `unidades.status` guarda apenas o estado **atual** de cada unidade, sem tabela de histórico de transições, então a base não permite comprovar retroativamente "o que acontece depois de um distrato". A validação correta é funcional, a ser feita manualmente: (a) após um distrato, a unidade some da lista de disponíveis; (b) `vendas.status_venda` vira `distrato` com `data_distrato` preenchida; (c) a unidade só reaparece como disponível após liberação manual explícita.
