# Log de Decisões

### 04/09/2026 (2) — Conferência do enunciado original: 3 gaps de aderência corrigidos

**Contexto:** releitura do PDF do enunciado ("Teste Analista de Negócio.pdf") ponto a ponto contra o sistema já implementado, para confirmar aderência antes da entrega/reunião. O assistente de linguagem natural foi testado ao vivo com uma pergunta livre fora do roteiro do projeto ("Quais os 3 empreendimentos com maior valor total de vendas ativas?") — respondeu com SQL real sobre `vw_vendas`/`vw_unidades`, resultado bruto e resposta rastreável, confirmando que o requisito "resposta fundamentada nos registros reais, não uma alucinação" está atendido.

**Gap 1 — README citava o modelo LLM errado.** Dizia `llama3-70b-8192`, mas o código (`text_to_sql.py` e `copiloto.py`) usa `openai/gpt-oss-20b`. Corrigido nas duas ocorrências do README.

**Gap 2 — Pergunta de Negócio 3 ("como isso distorceria uma métrica de clientes únicos ou de ticket médio, se não fosse tratado?") não tinha resposta quantificada**, só a conclusão de que não há duplicidade sob o critério rigoroso. Adicionada `resumo_distorcao_potencial()` em `analytics/clientes_duplicados.py`: quantifica que um critério ingênuo (só `nome`) fundiria os 234 cadastros dos 115 grupos de nome repetido, reduzindo "clientes únicos" em 119 registros (4,4% da base) e, por consequência, inflando o ticket médio aparente. Exposto em `core/validacoes.py::relatorio_qualidade_dado()` e no painel de Qualidade de Dados.

**Gap 3 — Pergunta de Negócio 4 ("em quantos meses/empreendimentos isso ocorre?") só respondia "quantos meses" na tela** (63 de 562); "quantos empreendimentos distintos" (18) só constava em `docs/business_rule.md`, não na interface. Adicionado `total_empreendimentos_afetados` ao retorno de `relatorio_qualidade_dado()` e exibido como métrica explícita no painel de Qualidade de Dados.

Testes novos em `tests/test_validacoes.py` fixam os 4 números centrais desta correção (115, 234, 119, 18) contra o banco real, para que qualquer regressão futura nesses cálculos quebre a suíte.

---

### 04/09/2026 — Revisão da camada de escrita: 3 gaps corrigidos antes da apresentação

**Contexto:** revisão simulando a lente do avaliador (foco prioritário na camada de escrita, ver critério da avaliação) sobre o código já implementado pelos dois agentes. Testado empiricamente contra uma cópia isolada do banco (não o arquivo real usado na demonstração).

**Gap 1 (crítico) — `registrar_venda()` aceitava `cliente_id` inexistente.** Reproduzido: passar `cliente_id=99999999` para uma unidade disponível gravava a venda normalmente, sem erro, criando uma referência órfã em `vendas.cliente_id`. Causa raiz: o SQLite não aplica as cláusulas `REFERENCES` do schema sem `PRAGMA foreign_keys = ON` por conexão, e essa pragma nunca era executada em `core/db.py`. **Correção:** pragma ativado em `get_connection()` (defesa em profundidade) + validação explícita em `registrar_venda()` (nova exceção `ClienteInvalidoError`) antes de qualquer escrita. Também separada a checagem de "unidade não encontrada" (`UnidadeNaoEncontradaError`, nova) de "unidade indisponível" (`UnidadeIndisponivelError`, já existente) — eram a mesma exceção antes, o que confundia dois motivos de recusa diferentes.

**Gap 2 (importante) — painel "Qualidade de Dados" afirmava checar integridade referencial e ausência de dupla venda ativa com valores fixos no código** (`[0, 0, 0, 0, 0]` escrito à mão), não uma consulta real. Coincidia com o estado atual do banco, mas não seria atualizado se o Gap 1 tivesse criado um registro órfão. **Correção:** `core/validacoes.py` ganhou `integridade_referencial()` e `unidades_com_dupla_venda_ativa()`, funções que consultam o banco de verdade; `app/pages/2_Qualidade_de_Dados.py` passou a exibir o resultado dessas funções em vez do array fixo.

**Gap 3 (importante) — testes de escrita (`registrar_venda`/`registrar_distrato`) rodavam direto contra `data/cambara_teste_tecnico.db`**, o mesmo banco usado na demonstração, com limpeza manual em cada teste. Uma falha no meio de um teste deixaria lixo permanente nesse arquivo. **Correção:** `tests/conftest.py` agora copia o banco para um arquivo temporário e aponta `DB_PATH` para essa cópia antes de qualquer teste rodar; a cópia é apagada ao final da sessão de testes.

Também corrigidos nesta revisão, de menor risco: validação de `valor_venda > 0` (antes aceitava R$ 0,00), mensagem específica para conflito de concorrência (`sqlite3.OperationalError` capturado antes do `except Exception` genérico), e validação de formato de e-mail para cliente novo na tela de Vendas e Distratos.

**Nota sobre a divisão de agentes:** os Gaps 2, 3 (parcialmente) e os itens de menor risco tocaram `app/pages/*.py` e `tests/`, fora do escopo original do agente "Dados & Regras" (ver decisão de 03/09/2026 abaixo). Optou-se por corrigir tudo numa única passada porque a revisão já havia identificado os gaps de ponta a ponta (núcleo + tela) e o prazo é curto — não porque a divisão em si deixou de valer para o desenvolvimento inicial.

---

### 03/09/2026 — Estratégia de execução: dois agentes em paralelo (Núcleo x Interface)

**Contexto:** entrega em 04/09, e até o momento nenhuma linha de aplicação foi escrita (só exploração de dados e regras de negócio, que já estão fechadas). Decidido paralelizar o trabalho em dois agentes Claude, cada um com um escopo de arquivos exclusivo, para reduzir o tempo total sem gerar retrabalho de integração.

**Decisão:** divisão por camada, não por feature. Um agente ("Dados & Regras") implementa `core/`, `analytics/`, `nl_assistant/` e os testes de regra de negócio. Outro agente ("Interface") implementa só `app/main.py` e `app/pages/*.py`, consumindo as funções do primeiro. A divisão por camada foi escolhida em vez de divisão por feature vertical (ex: um agente cuida de "vendas" ponta a ponta, outro de "analytics" ponta a ponta) porque a fronteira entre lógica de negócio e Streamlit já era a própria estrutura de pastas sugerida no roadmap — ou seja, zero arquivo é tocado pelos dois agentes ao mesmo tempo, o que elimina risco de conflito de merge sem precisar de git worktree (que teria custo de setup que não compensa no tempo restante).

**Pré-requisito que viabiliza o paralelismo:** um contrato de interface (`docs/interface_contrato.md`) escrito antes de qualquer agente começar a codar, com a assinatura exata de cada função do núcleo. Isso permite que o agente de Interface escreva as páginas Streamlit chamando funções que ainda não existem, sem esperar o outro agente terminar.

**Achado durante a escrita do contrato:** o critério de normalização de status (regra 1 de `business_rule.md`) resolve grafia/acento, mas não resolve sozinho a 4ª variação encontrada em `vendas.status_venda` (`"Distratada"`, distinta de `"distrato"` após normalização simples). Isso foi incorporado explicitamente ao contrato como responsabilidade de `esta_distratada()`, para não vazar para a camada de escrita — o componente mais observado da avaliação.
