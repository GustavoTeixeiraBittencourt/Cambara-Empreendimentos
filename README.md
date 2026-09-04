# Teste Técnico — Analista de Soluções de Negócio
---
Por: Gustavo Teixeira Bittencourt de Oliveira 

Este projeto foi desenvolvido como parte do processo seletivo para a posição de **Analista de Soluções de Negócio (Full Stack)** da **Cambará Empreendimentos S.A.**

O desafio consiste em transformar uma base de dados de negócio existente, composta por informações de empreendimentos, unidades, clientes, vendas, andamento de obras, resultados financeiros e usuários, em uma **aplicação capaz de apoiar decisões de negócio de forma confiável e rastreável**.

A base disponibilizada possui mais de 9 mil registros distribuídos em 7 tabelas e apresenta características comuns a cenários reais, como inconsistências de cadastro, duplicidades, valores nulos e divergências entre valores reportados e valores que podem ser recalculados a partir dos dados. Dessa forma, o desafio não está apenas na implementação da aplicação, mas principalmente na **interpretação dos dados, definição de regras de negócio e explicitação das premissas adotadas**.

A solução desenvolvida contempla quatro frentes principais:

- **Autenticação**, utilizando os usuários disponibilizados na base;
- **Camada analítica**, com indicadores e visualizações voltados às principais perguntas de negócio;
- **Camada de escrita**, permitindo o registro de vendas e distratos, respeitando as regras de disponibilidade das unidades;
- **Assistente de perguntas em linguagem natural**, capaz de consultar os dados reais e fornecer respostas rastreáveis às informações presentes na base.

O objetivo deste projeto é, portanto, demonstrar não somente a capacidade de desenvolver uma aplicação ponta a ponta, mas também a capacidade de **entender um problema de negócio, transformar dados imperfeitos em informações confiáveis, estabelecer premissas claras e construir uma solução que conecte tecnologia às necessidades do negócio**.

## Resumo executivo

- **Problema:** a base da Cambará tem mais de 9 mil registros com inconsistências reais — grafias diferentes para o mesmo status, campos que se contradizem entre si, divergência entre resultado financeiro reportado e recalculado. Sem uma camada que trate isso, qualquer decisão tomada em cima desses números corre o risco de estar sub-contando ou super-contando a realidade.
- **O que foi entregue:** uma aplicação que (1) transforma os dados brutos em 4 indicadores de negócio auditáveis, (2) impede operacionalmente a venda de uma unidade já vendida/reservada e controla o fluxo de distrato, e (3) responde perguntas livres sobre os dados reais sempre mostrando a consulta SQL usada — nenhuma resposta é dada sem se poder conferir de onde ela veio.
- **Principais achados nos dados** (números reais, extraídos do banco — fórmula e premissa completas na seção [Perguntas de negócio e principais achados](#perguntas-de-negócio-e-principais-achados)):
  - **Velocidade de vendas:** média geral de 62% das unidades ofertadas estão vendidas hoje. Três empreendimentos concentram o pior desempenho — **Essência Living (6,8%)**, **Atelier Tower (18,3%)** e **Cume Tower (24,7%)** — candidatos naturais a ação comercial prioritária.
  - **Estouro de custo:** **15 dos 22 empreendimentos (68%)** estão com custo realizado acima do orçado, somando **R$ 16 milhões** em estouro acumulado. Pior caso: **Panorama do Parque**, R$ 4,2 milhões (3,2%) acima do orçamento.
  - **Divergência financeira:** **63 de 562 registros mensais (11,2%)**, em **18 dos 22 empreendimentos**, têm resultado reportado divergente do recalculado em mais de R$ 1 — sinal de que o número reportado sozinho não deveria ser tratado como fonte única de verdade.
  - **Clientes duplicados:** **0 grupos** sob o critério rigoroso adotado (nome + cidade + data de cadastro idênticos). Um critério ingênuo (só nome) fundiria indevidamente 119 cadastros — a base tem muitos homônimos, não duplicidade real.
- **Limitações assumidas conscientemente:** sem CPF/telefone na base, a deduplicação de clientes fica limitada a um critério conservador (evita falso positivo, mas pode deixar passar duplicidade real); a autenticação usa hash simples sem salt, adequado ao escopo do teste, não a produção. Lista completa na seção [Limitações conhecidas](#limitações-conhecidas).

## Perguntas de negócio e principais achados

As 4 perguntas de negócio do teste são respondidas no **Dashboard** (`app/pages/Dashboard.py`), cada uma calculada em `app/analytics/` — nunca com número fixo digitado na tela. Abaixo, a pergunta original, a premissa adotada e o resultado real encontrado na base. A fórmula completa, a justificativa de cada premissa e a validação em banco de cada uma estão documentadas em **[`docs/business_rule.md`](docs/business_rule.md)**.

### 1. Velocidade de vendas

- **Pergunta:** quais empreendimentos estão performando mal em vendas?
- **Premissa:** "vendido" = venda ativa, ou seja, não distratada (regras 1 a 4); o denominador é todas as unidades cadastradas, mesmo em empreendimentos com obra suspensa (regra 5) — excluir os suspensos infla artificialmente a métrica justamente dos casos que mais precisam de atenção.
- **Resultado:** média geral de **62%** de velocidade de vendas. Os três piores desempenhos são **Essência Living (6,8%, 13 de 190 unidades vendidas)**, **Atelier Tower (18,3%)** e **Cume Tower (24,7%)**.

### 2. Estouro de custo

- **Pergunta:** quais empreendimentos estão gastando acima do orçado?
- **Premissa:** custo acumulado realizado vs. orçado por empreendimento, a partir de `obra_andamento`.
- **Resultado:** **15 dos 22 empreendimentos (68%)** estão com custo realizado acima do orçado, somando **R$ 16 milhões** em estouro acumulado. O pior caso é **Panorama do Parque**, R$ 4,17 milhões (3,2%) acima do orçamento, seguido de Estúdio Amazônia (R$ 2,38 milhões, 3,0%) e Alto Amazônia (R$ 2,26 milhões, 2,7%).

### 3. Clientes duplicados

- **Pergunta:** existem clientes duplicados na base?
- **Premissa:** sem CPF nem telefone disponíveis, duplicidade = nome + cidade + data de cadastro **todos** idênticos (critério conservador, regra 6 — minimiza falso positivo).
- **Resultado:** **0 grupos** duplicados sob esse critério. Achado relevante: dos 115 grupos de nome repetido (234 cadastros), a esmagadora maioria tem cidade e data de cadastro diferentes — são homônimos, não duplicidade. Um critério ingênuo que considerasse só o nome fundiria indevidamente **119 registros (4,4% da base de clientes)**, inflando artificialmente o ticket médio por cliente.

### 4. Divergência financeira

- **Pergunta:** o resultado financeiro reportado bate com o que os dados brutos sustentam?
- **Premissa:** tolerância de R$ 1,00 de arredondamento; divergência absoluta acima disso é considerada inconsistência real (regra 7).
- **Resultado:** **63 de 562 registros mensais (11,2%)**, distribuídos em **18 dos 22 empreendimentos**, têm divergência acima da tolerância — em alguns casos, a diferença passa de R$ 1 milhão em módulo.

## Páginas da aplicação

A navegação é feita pela barra lateral do Streamlit (`app/main.py`), que só mostra as páginas depois do login. Cada tela é um arquivo independente em `app/pages/`.

### Login (`app/main.py`)

Formulário simples de e-mail/senha, validado contra a tabela `usuarios` (`core/auth.py`, hash SHA-256 — ver regra 8 em `docs/business_rule.md`). Também é onde vive o CSS global do "tema executivo" (cores, cards, cabeçalhos) reutilizado por todas as páginas.

### Dashboard (`app/pages/Dashboard.py`)

Tela inicial após o login. Responde às **4 perguntas de negócio do teste**, uma por aba, cada uma calculada em `app/analytics/` (nunca com número fixo digitado na tela) — os resultados de cada uma estão resumidos acima, em [Perguntas de negócio e principais achados](#perguntas-de-negócio-e-principais-achados):

- **Velocidade de vendas** (`analytics/velocidade_vendas.py`) — por empreendimento, qual fração das unidades ofertadas segue vendida hoje (descontando distratos). Gráfico de barras + tabela com os 3 empreendimentos que mais precisam de atenção.
- **Estouro de custo** (`analytics/estouro_custo.py`) — compara custo orçado x custo realizado acumulado por empreendimento; destaca quem está gastando acima do planejado.
- **Clientes duplicados** (`analytics/clientes_duplicados.py`) — cadastros com nome, cidade e data de cadastro idênticos (critério conservador, ver regra 6).
- **Divergência financeira** (`analytics/divergencia_financeira.py`) — resultado mensal reportado x recalculado a partir dos dados brutos, com tolerância de R$ 1,00 de arredondamento.

Cada aba tem um bloco de "Insight + Recomendação" em linguagem de negócio, gerado a partir do pior caso encontrado nos dados — não é texto fixo.

### Qualidade de Dados (`app/pages/Qualidade_de_Dados.py`)

Painel de governança que expõe, em tempo real e direto do banco (`core/validacoes.py::relatorio_qualidade_dado`), tudo o que sustenta a confiabilidade dos números do Dashboard:

- Volume de registros por tabela;
- Campos sem preenchimento (nulos) e por que cada caso é esperado ou não;
- Grafias diferentes do mesmo status, antes/depois da normalização;
- Conflitos entre `status_venda` e `data_distrato` (já corrigidos pela regra de precedência);
- Divergências financeiras acima do tolerado;
- Integridade referencial entre as 7 tabelas (registros "órfãos");
- Por que o critério de duplicidade de clientes não encontra falsos positivos, com a quantificação de quanto um critério ingênuo distorceria o ticket médio;
- Consistência do percentual de conclusão das obras (faixa 0–100%).

Esta é a página que "mostra o trabalho" por trás de cada número do Dashboard — ver também `docs/data_exploration.md`.

### Vendas e Distratos (`app/pages/Vendas_e_Distratos.py`)

A **camada de escrita** da aplicação — único lugar do sistema que grava em `vendas`/`unidades`/`clientes`. Duas abas:

- **Registrar venda**: lista só unidades com status normalizado `disponivel` (`core/regras_negocio.py::unidades_disponiveis`); permite escolher um cliente já cadastrado ou cadastrar um novo (com `data_cadastro` preenchida automaticamente); valida e-mail e valor da venda antes de submeter. Toda a gravação passa por `registrar_venda`, que roda dentro de uma transação e valida `cliente_id`/`unidade_id` no backend, não só na tela.
- **Registrar distrato**: lista só vendas ativas (`esta_ativa`); ao confirmar, `registrar_distrato` marca a venda como distratada e muda o status da unidade para `distrato` — **não** para `disponivel` (regra 9: liberar a unidade de novo exige ação manual, não é automático).

Erros de regra de negócio (unidade indisponível, cliente inválido, venda já distratada, corrida entre duas transações concorrentes) aparecem como mensagem clara na tela, nunca como stack trace.

### Assistente (`app/pages/Assistente.py`)

Página dedicada ao assistente de linguagem natural em **text-to-SQL** (`nl_assistant/text_to_sql.py`): o usuário digita uma pergunta em português, o LLM gera um `SELECT` sobre o schema real (priorizando as views normalizadas `vw_vendas`/`vw_unidades`), a consulta é validada por um guardrail (`nl_assistant/guardrails.py`) e executada contra o banco. **SQL gerado e resultado bruto ficam sempre visíveis** abaixo da resposta, para rastreabilidade — nada é respondido sem mostrar de onde veio. Detalhes da abordagem e o roteiro de perguntas testadas estão na seção [Assistente de linguagem natural](#assistente-de-linguagem-natural) abaixo.

### Copiloto flutuante (`app/components/assistant_widget.py`)

Presente em todas as páginas logadas (botão flutuante no canto inferior direito). É um assistente **diferente** do da página Assistente: não gera SQL nem lê a base diretamente — ele recebe um resumo já calculado (os mesmos números do Dashboard e da Qualidade de Dados, em JSON) e responde só com base nesse resumo (`nl_assistant/copiloto.py`), com perguntas sugeridas prontas (ex.: "Quais empreendimentos precisam de atenção?"). Serve para perguntas rápidas de interpretação dos indicadores já na tela, sem sair da página atual; para perguntas livres sobre dados que não estão nesse resumo, use a página Assistente.

## Stack utilizada

- **Python 3.12**
- **Streamlit 1.63** — interface (multi-página, autenticação simples via `st.session_state`)
- **SQLite** — banco de dados fornecido (`data/cambara_teste_tecnico.db`), acessado via `sqlite3` da stdlib
- **Groq** (`openai/gpt-oss-20b`) — LLM usado no assistente de linguagem natural (text-to-SQL) e no copiloto flutuante
- **pandas** / **altair** — manipulação tabular e gráficos nas telas analíticas
- **pytest** — suíte de testes (`tests/`)

## Arquitetura

Camadas simples, sem overengineering — nasceram dos requisitos, não de um padrão imposto de antemão:

```
app/
  main.py                    # login + navegação entre páginas + CSS global (Streamlit)
  components/
    assistant_widget.py       # copiloto flutuante (popover), presente em todas as páginas logadas
  pages/                      # 1 arquivo Streamlit por tela
    Dashboard.py
    Qualidade_de_Dados.py
    Vendas_e_Distratos.py
    Assistente.py
  core/
    db.py                     # acesso a dados (conexão SQLite, run_query, transaction)
    regras_negocio.py         # regras de negócio (normalização de status, venda, distrato)
    validacoes.py             # painel de qualidade de dado
    auth.py                   # autenticação (SHA-256)
    exceptions.py             # exceções de domínio
  analytics/                  # uma pergunta de negócio por módulo
  nl_assistant/                # assistente de linguagem natural (text-to-SQL + guardrails) e copiloto
  format_br.py                 # formatação de número/moeda/percentual em pt-BR
sql/
  views.sql                    # views de normalização de status (vw_vendas, vw_unidades)
scripts/
  setup_senhas.py               # setup único: hash das senhas dos usuários
  aplicar_views.py               # setup único: cria as views de sql/views.sql no banco
docs/
  business_rule.md                # as 9 regras de negócio formais (Problema→Regra→Fórmula→Validação)
  data_exploration.md              # achados da exploração da base (grafias, nulos, conflitos)
  interface_contrato.md             # contrato de assinatura das funções do núcleo
  decisions.md                      # log de decisões de execução do projeto
  roteiro_validacao_assistente.md    # roteiro de perguntas testadas no assistente, com gabarito
tests/                               # pytest, rodado contra o banco real
```

A camada de escrita (`registrar_venda`, `registrar_distrato`) é o único lugar que altera as tabelas `vendas`/`unidades` — sempre dentro de uma transação atômica (`BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`). Nada mais na aplicação faz `UPDATE`/`INSERT`/`DELETE` nas tabelas originais: leitura e normalização de status passam por `core/regras_negocio.py` (usado tanto pela validação de escrita quanto pelas telas analíticas) ou pelas views somente-leitura em `sql/views.sql` — nunca um valor de status é reescrito retroativamente na base.

## Instalação

```bash
git clone <repositório>
cd Cambara
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # e preencha GROQ_API_KEY (necessário só para o Assistente e o copiloto)
```

`GROQ_API_KEY` é usada exclusivamente pela página **Assistente** (`app/pages/Assistente.py`) e pelo copiloto flutuante (`app/components/assistant_widget.py`); as demais telas funcionam sem ela.

## Execução

Rodar sempre a partir da raiz do repositório (o Streamlit adiciona `app/` ao `sys.path` automaticamente):

```bash
# 1. Setup único — só precisa rodar uma vez por cópia do banco
python scripts/setup_senhas.py     # troca o placeholder de senha pelo hash de "cambara2026"
python scripts/aplicar_views.py    # cria vw_vendas/vw_unidades (sql/views.sql) — já aplicado no banco entregue

# 2. Rodar a aplicação
streamlit run app/main.py
```

Login: qualquer e-mail de `usuarios` na base, senha **`cambara2026`** (ver regra 8 em `docs/business_rule.md`).

Testes:

```bash
python -m pytest tests/ -v
```

## Como ler os dados

O banco é um único arquivo SQLite em `data/cambara_teste_tecnico.db`, com 7 tabelas: `empreendimentos`, `unidades`, `clientes`, `vendas`, `obra_andamento`, `financeiro_mensal`, `usuarios`.

### Direto no banco (fora da aplicação)

Qualquer cliente SQLite serve — linha de comando ou uma ferramenta gráfica como o [DB Browser for SQLite](https://sqlitebrowser.org/):

```bash
sqlite3 data/cambara_teste_tecnico.db
sqlite> .tables
sqlite> .schema vendas
sqlite> SELECT COUNT(*) FROM unidades;
```

**Atenção ao ler as colunas brutas de status** (`unidades.status`, `vendas.status_venda`): elas têm grafias diferentes para o mesmo valor (`Vendida`, `VENDIDA`, `vendida`, ...) — uma consulta direta sobre essas colunas sub-conta o resultado real. Para leitura já normalizada, use as views somente-leitura criadas por `scripts/aplicar_views.py` (definidas em `sql/views.sql`):

```sql
SELECT status_venda_normalizado, COUNT(*) FROM vw_vendas GROUP BY 1;    -- 'ativa' | 'distratada'
SELECT status_normalizado, COUNT(*) FROM vw_unidades GROUP BY 1;        -- 'vendida' | 'disponivel' | 'reservada' | 'distrato'
```

Essas views funcionam em qualquer cliente SQLite, não só dentro da aplicação Python — foram pensadas para isso. A lógica completa de normalização (por que cada grafia cai em qual categoria, e por que `data_distrato` tem precedência sobre o texto do status) está documentada em `docs/business_rule.md` (regras 1 a 3) e o levantamento bruto que originou essas regras está em `docs/data_exploration.md`.

### Dentro da aplicação (Python)

Toda leitura passa por `app/core/db.py`:

```python
from core.db import run_query

run_query("SELECT * FROM empreendimentos WHERE id = ?", (1,))   # -> list[dict]
```

`get_connection()` abre a conexão com `row_factory=sqlite3.Row` e `PRAGMA foreign_keys = ON` (sem esse pragma o SQLite não aplica as `REFERENCES` do schema). Escritas (só usadas por `registrar_venda`/`registrar_distrato`) passam pelo context manager `transaction()`, que abre `BEGIN IMMEDIATE` e faz `COMMIT`/`ROLLBACK` automaticamente. O caminho do banco pode ser sobrescrito com a variável de ambiente `DB_PATH` (por exemplo, para apontar os testes para uma cópia do banco).

O contrato completo de cada função do núcleo (parâmetros, exceções, o que persiste no banco) está em **[`docs/interface_contrato.md`](docs/interface_contrato.md)**.

## Regras de negócio

As 9 regras de negócio formais (normalização de status, fonte de verdade em conflitos, definição de "venda ativa", critério de cliente duplicado, tolerância de divergência financeira, comportamento pós-distrato etc.) estão documentadas em **[`docs/business_rule.md`](docs/business_rule.md)**, no formato Problema → Regra → Fórmula → Exemplo → Impacto → Implementação → Validação — cada uma com o número de registros afetados conferido diretamente no banco.

Duas colunas de status merecem atenção porque são tratadas de forma diferente uma da outra, por decisão deliberada e não por descuido:

- **`vendas.status_venda`**: 6 grafias brutas (`Ativa, ativa, ATIVA, Distrato, distrato, Distratada`) colapsam para **2 categorias de negócio: `ativa` e `distratada`**. `data_distrato` preenchida tem precedência sobre o texto do status.
- **`unidades.status`**: 11 grafias brutas colapsam para **4 categorias: `vendida`, `disponivel`, `reservada`, `distrato`** — aqui o rótulo de distrato permanece `distrato` (substantivo), não `distratada`; é uma coluna e uma decisão de nomenclatura independentes da anterior.

## Tratamento de dados

A exploração completa da base (nulos, grafias distintas, duplicidades, conflitos entre campos) está em **[`docs/data_exploration.md`](docs/data_exploration.md)**. O painel **Qualidade de Dados** da aplicação (`app/pages/Qualidade_de_Dados.py`) expõe esses mesmos achados em tempo real, direto do banco — não são números fixos digitados na tela.

Como o banco fornecido **não pode ser alterado** (nenhuma linha de `unidades`/`vendas` é reescrita para "corrigir" uma grafia), a normalização acontece em dois lugares equivalentes e testados entre si (`tests/test_views.py`):

- **Python** (`core/regras_negocio.py`) — usado pela camada de escrita e pelas telas Streamlit;
- **SQL** (`sql/views.sql`, views `vw_vendas`/`vw_unidades`) — views somente-leitura (DDL, nunca `UPDATE`/`DELETE` sobre uma linha existente), pensadas para consulta direta (inclusive fora da aplicação, em qualquer cliente SQLite) e para o assistente de linguagem natural.

## Assistente de linguagem natural

Abordagem: **text-to-SQL** com um LLM (Groq, `openai/gpt-oss-20b`), restrito a `SELECT` único (`app/nl_assistant/guardrails.py` bloqueia qualquer outra instrução ou múltiplos statements antes de executar). SQL e resultado são sempre expostos na tela — nada é respondido sem mostrar a consulta que gerou a resposta, para rastreabilidade. Essa é a abordagem usada pela página **Assistente**; o copiloto flutuante (descrito em [Páginas da aplicação](#copiloto-flutuante-appcomponentsassistant_widgetpy)) é uma segunda abordagem, mais restrita, sobre um resumo pré-calculado — não gera SQL.

Para reduzir o risco de o modelo reproduzir errado a lógica de normalização de status a cada pergunta, o schema passado ao LLM aponta primeiro para `vw_vendas`/`vw_unidades` (status já normalizado, 2 e 4 categorias respectivamente) em vez das tabelas brutas — o modelo só precisa filtrar `status_venda_normalizado = 'distratada'`, por exemplo, em vez de reconstruir a regra de sinônimos em SQL toda vez.

Roteiro de perguntas testadas (com SQL, resultado e gabarito reais) para validar que o assistente responde com base nos dados e não alucina: **[`docs/roteiro_validacao_assistente.md`](docs/roteiro_validacao_assistente.md)**.

## Limitações conhecidas

- **Clientes duplicados**: sem CPF/telefone na base, o critério (nome + cidade + data de cadastro idênticos) é deliberadamente conservador para não gerar falso positivo — resultado atual: 0 grupos. Um critério mais agressivo seria probabilístico, não determinístico (ver regra 6).
- **Assistente de linguagem natural**: a robustez depende do LLM seguir a instrução de usar as views normalizadas; o guardrail garante que a consulta é só leitura, mas não garante que o SQL gerado seja sempre semanticamente ótimo. Testado e confirmado (ver `docs/roteiro_validacao_assistente.md`, seção 5): para uma pergunta fora do schema (ex.: número de funcionários — a base não tem essa tabela), o assistente da página dedicada não avisa que a informação não existe — ele gera uma consulta trivial que retorna 0 e apresenta como resposta real, em vez de dizer explicitamente "essa informação não está disponível" (o widget flutuante, `nl_assistant/copiloto.py`, já tem essa instrução no prompt; a página dedicada, `nl_assistant/text_to_sql.py`, ainda não).
- **Senha de usuário**: hash SHA-256 simples, sem salt (ver regra 8) — simplificação documentada e adequada ao escopo do teste; uma versão de produção exigiria bcrypt/argon2.
- **Views (`sql/views.sql`)**: aplicadas uma única vez via `scripts/aplicar_views.py`, não recriadas a cada conexão — se o banco for substituído por uma cópia sem as views, rode o script novamente.

## Documentação complementar

Além dos documentos já linkados nas seções acima, a pasta `docs/` reúne todo o raciocínio por trás das decisões do projeto — a ideia é que qualquer afirmação feita na aplicação ou neste README possa ser conferida na fonte:

| Documento | Conteúdo |
|---|---|
| [`docs/business_rule.md`](docs/business_rule.md) | As 9 regras de negócio formais, com fórmula, exemplo e impacto medido no banco. |
| [`docs/data_exploration.md`](docs/data_exploration.md) | Exploração bruta da base (volumes, grafias, nulos, conflitos) — o que sustenta as regras. |
| [`docs/interface_contrato.md`](docs/interface_contrato.md) | Contrato de assinatura de cada função do núcleo (parâmetros, exceções, retorno). |
| [`docs/decisions.md`](docs/decisions.md) | Log cronológico de decisões de execução, trade-offs e correções de aderência ao enunciado. |
| [`docs/roteiro_validacao_assistente.md`](docs/roteiro_validacao_assistente.md) | Perguntas testadas no assistente de linguagem natural, com SQL, resultado e gabarito reais. |