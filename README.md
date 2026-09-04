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

## Stack utilizada

- **Python 3.12**
- **Streamlit 1.63** — interface (multi-página, autenticação simples via `st.session_state`)
- **SQLite** — banco de dados fornecido (`data/cambara_teste_tecnico.db`), acessado via `sqlite3` da stdlib
- **Groq** (`openai/gpt-oss-20b`) — LLM usado no assistente de linguagem natural (text-to-SQL)
- **pandas** — manipulação tabular nas telas analíticas
- **pytest** — suíte de testes (`tests/`)

## Arquitetura

Camadas simples, sem overengineering — nasceram dos requisitos, não de um padrão imposto de antemão:

```
app/
  main.py              # login + navegação entre páginas (Streamlit)
  pages/                # 1 arquivo Streamlit por tela
  core/
    db.py               # acesso a dados (conexão SQLite, run_query, transaction)
    regras_negocio.py    # regras de negócio (normalização de status, venda, distrato)
    validacoes.py        # painel de qualidade de dado
    auth.py              # autenticação (SHA-256)
    exceptions.py         # exceções de domínio
  analytics/             # uma pergunta de negócio por módulo
  nl_assistant/           # assistente de linguagem natural (text-to-SQL + guardrails)
sql/
  views.sql              # views de normalização de status (vw_vendas, vw_unidades)
scripts/
  setup_senhas.py         # setup único: hash das senhas dos usuários
  aplicar_views.py         # setup único: cria as views de sql/views.sql no banco
docs/
  business_rule.md         # as 9 regras de negócio formais (Problema→Regra→Fórmula→Validação)
  data_exploration.md       # achados da exploração da base (grafias, nulos, conflitos)
  interface_contrato.md      # contrato de assinatura das funções do núcleo
  decisions.md               # log de decisões de execução do projeto
tests/                        # pytest, rodado contra o banco real
```

A camada de escrita (`registrar_venda`, `registrar_distrato`) é o único lugar que altera as tabelas `vendas`/`unidades` — sempre dentro de uma transação atômica (`BEGIN`/`COMMIT`/`ROLLBACK`). Nada mais na aplicação faz `UPDATE`/`INSERT`/`DELETE` nas tabelas originais: leitura e normalização de status passam por `core/regras_negocio.py` (usado tanto pela validação de escrita quanto pelas telas analíticas) ou pelas views somente-leitura em `sql/views.sql` — nunca um valor de status é reescrito retroativamente na base.

## Instalação

```bash
git clone <repositório>
cd Cambara
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # e preencha GROQ_API_KEY (necessário só para o Assistente)
```

`GROQ_API_KEY` é usada exclusivamente pela tela **Assistente** (`app/pages/4_Assistente.py`); as demais telas funcionam sem ela.

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

## Regras de negócio

As 9 regras de negócio formais (normalização de status, fonte de verdade em conflitos, definição de "venda ativa", critério de cliente duplicado, tolerância de divergência financeira, comportamento pós-distrato etc.) estão documentadas em **[`docs/business_rule.md`](docs/business_rule.md)**, no formato Problema → Regra → Fórmula → Exemplo → Impacto → Implementação → Validação — cada uma com o número de registros afetados conferido diretamente no banco.

Duas colunas de status merecem atenção porque são tratadas de forma diferente uma da outra, por decisão deliberada e não por descuido:

- **`vendas.status_venda`**: 6 grafias brutas (`Ativa, ativa, ATIVA, Distrato, distrato, Distratada`) colapsam para **2 categorias de negócio: `ativa` e `distratada`**. `data_distrato` preenchida tem precedência sobre o texto do status.
- **`unidades.status`**: 11 grafias brutas colapsam para **4 categorias: `vendida`, `disponivel`, `reservada`, `distrato`** — aqui o rótulo de distrato permanece `distrato` (substantivo), não `distratada`; é uma coluna e uma decisão de nomenclatura independentes da anterior.

## Tratamento de dados

A exploração completa da base (nulos, grafias distintas, duplicidades, conflitos entre campos) está em **[`docs/data_exploration.md`](docs/data_exploration.md)**. O painel **Qualidade de Dados** da aplicação (`app/pages/2_Qualidade_de_Dados.py`) expõe esses mesmos achados em tempo real, direto do banco — não são números fixos digitados na tela.

Como o banco fornecido **não pode ser alterado** (nenhuma linha de `unidades`/`vendas` é reescrita para "corrigir" uma grafia), a normalização acontece em dois lugares equivalentes e testados entre si (`tests/test_views.py`):

- **Python** (`core/regras_negocio.py`) — usado pela camada de escrita e pelas telas Streamlit;
- **SQL** (`sql/views.sql`, views `vw_vendas`/`vw_unidades`) — views somente-leitura (DDL, nunca `UPDATE`/`DELETE` sobre uma linha existente), pensadas para consulta direta (inclusive fora da aplicação, em qualquer cliente SQLite) e para o assistente de linguagem natural.

## Perguntas de negócio / métricas

As 4 perguntas de negócio do teste (velocidade de vendas, estouro de custo, clientes duplicados, divergência financeira) são calculadas em `app/analytics/` e exibidas no **Dashboard**. Cada métrica, sua fórmula e as premissas assumidas (ex.: o que conta como "unidade ofertada", tolerância de arredondamento financeiro, critério de cliente duplicado) estão documentadas junto da regra correspondente em `docs/business_rule.md`.

## Assistente de linguagem natural

Abordagem: **text-to-SQL** com um LLM (Groq, `openai/gpt-oss-20b`), restrito a `SELECT` único (`app/nl_assistant/guardrails.py` bloqueia qualquer outra instrução ou múltiplos statements antes de executar). SQL e resultado são sempre expostos na tela — nada é respondido sem mostrar a consulta que gerou a resposta, para rastreabilidade.

Para reduzir o risco de o modelo reproduzir errado a lógica de normalização de status a cada pergunta, o schema passado ao LLM aponta primeiro para `vw_vendas`/`vw_unidades` (status já normalizado, 2 e 4 categorias respectivamente) em vez das tabelas brutas — o modelo só precisa filtrar `status_venda_normalizado = 'distratada'`, por exemplo, em vez de reconstruir a regra de sinônimos em SQL toda vez.

Roteiro de perguntas testadas (com SQL, resultado e gabarito reais) para validar que o assistente responde com base nos dados e não alucina: **[`docs/roteiro_validacao_assistente.md`](docs/roteiro_validacao_assistente.md)**.

## Limitações conhecidas

- **Clientes duplicados**: sem CPF/telefone na base, o critério (nome + cidade + data de cadastro idênticos) é deliberadamente conservador para não gerar falso positivo — resultado atual: 0 grupos. Um critério mais agressivo seria probabilístico, não determinístico (ver regra 6).
- **Assistente de linguagem natural**: a robustez depende do LLM seguir a instrução de usar as views normalizadas; o guardrail garante que a consulta é só leitura, mas não garante que o SQL gerado seja sempre semanticamente ótimo. Testado e confirmado (ver `docs/roteiro_validacao_assistente.md`, seção 5): para uma pergunta fora do schema (ex.: número de funcionários — a base não tem essa tabela), o assistente da página dedicada não avisa que a informação não existe — ele gera uma consulta trivial que retorna 0 e apresenta como resposta real, em vez de dizer explicitamente "essa informação não está disponível" (o widget flutuante, `nl_assistant/copiloto.py`, já tem essa instrução no prompt; a página dedicada, `nl_assistant/text_to_sql.py`, ainda não).
- **Senha de usuário**: hash SHA-256 simples, sem salt (ver regra 8) — simplificação documentada e adequada ao escopo do teste; uma versão de produção exigiria bcrypt/argon2.
- **Views (`sql/views.sql`)**: aplicadas uma única vez via `scripts/aplicar_views.py`, não recriadas a cada conexão — se o banco for substituído por uma cópia sem as views, rode o script novamente.

## Decisões importantes

O histórico de decisões de execução do projeto (estratégia, prioridades, trade-offs) está em **[`docs/decisions.md`](docs/decisions.md)**. O contrato de assinatura de cada função do núcleo (parâmetros, exceções, o que persiste no banco) está em **[`docs/interface_contrato.md`](docs/interface_contrato.md)**.



