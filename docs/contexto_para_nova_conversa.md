# Contexto — Teste Técnico Cambará (para retomar em nova conversa)

> Gerado em 03/09/2026, com base no estado real do repositório (git log + estrutura de arquivos) e nas decisões já tomadas. Cole este arquivo no início de uma nova conversa para retomar o trabalho sem perder contexto.

---

## 1. O teste, em uma frase

Analista de Soluções de Negócio (Full Stack) — Grupo Quadra/Cambará Empreendimentos S.A. Construir, em 3 dias, uma aplicação Python + Streamlit sobre o SQLite `cambara_teste_tecnico.db`, com 4 componentes obrigatórios: login (tabela `usuarios`), camada analítica (4 perguntas de negócio), **camada de escrita** (registrar venda e distrato, gravando de verdade no banco — é o item mais observado da avaliação) e assistente de linguagem natural rastreável (text-to-SQL, só leitura). Prazo: quarta 02/09 (Dia 1), quinta 03/09 (Dia 2), sexta 04/09 até a entrega (Dia 3). Apresentação em 08/09.

## 2. Quem avalia — Yan Machado Lopes

Gerente de Estratégia do Grupo Quadra, ~6 meses no cargo, formação em gestão executiva (FDC), não engenharia. Gerencia o time técnico mas não é um par técnico. Avalia mais pelo **impacto de negócio e clareza da decisão** do que pela sofisticação técnica — prefere respostas curtas em formato situação → ação → resultado, e cada decisão técnica precisa terminar numa frase de negócio ("decidi X porque Y, e isso evita Z"). Não costuma pedir profundidade de implementação não solicitada, mas pergunta "como você validou isso?" — então a implementação não pode ser frágil, só não precisa ser mostrada em detalhe se não pedirem. Perfil completo em `context_avaliador_yan_lopes.md` (documento do projeto Claude, não está no repositório de código).

## 3. Status real do projeto (conferido via `git log` e estrutura de pastas — não é estimativa)

**Commits até agora** (todos em 02–03/09, branch `development`):
1. `initial commit`
2. `.env.example` com variável do Groq
3. `.gitignore` (ignora `venv/` e `.env`)
4. `requirements.txt` (streamlit, groq, pandas, altair, etc. — populado e completo)
5. `docs/data_exploration.md` — exploração de dados completa
6. `docs/business_rule.md` — as 9 regras de negócio, fechadas e conferidas contra o banco
7. `data/cambara_teste_tecnico.db` — banco versionado no repo

**Pendente de commit no working directory:** `README.md` modificado (rascunho inicial já escrito, ainda não commitado), `docs/decisions.md` (criado, vazio), `docs/data_exploration.pdf` e `roadmap_teste_cambara.pdf` (não rastreados).

**⚠️ Ponto de atenção real de cronograma:** as pastas `app/`, `core/`, `src/`, `sql/`, `tests/` existem no disco mas estão **completamente vazias** — nenhum arquivo `.py` foi criado ainda. Ou seja, **nenhuma linha de código da aplicação foi escrita até agora.** Segundo o roadmap, o Dia 1 (02/09) deveria terminar com login funcionando e a primeira versão da camada de escrita gravando no banco — isso não aconteceu. Hoje é Dia 2 (03/09) e o projeto ainda está no ponto que o roadmap esperava para o **fim da manhã do Dia 1**. Isso não é motivo de pânico, mas precisa ser tratado como prioridade máxima na próxima sessão: pular qualquer refinamento de documentação e ir direto para setup + camada de escrita.

## 4. O que já está pronto (Bloco 1 e 2 do Dia 1 — completos)

- **Exploração de dados completa** (`docs/data_exploration.md`): nulos mapeados em todas as tabelas, integridade referencial das 5 relações confirmada (zero órfãos), inconsistência de grafia em `unidades.status` e `vendas.status_venda` documentada, achado de conflito `status_venda`/`data_distrato` (37 casos), duplicidade de clientes investigada (115 grupos de nome repetido, mas 0 sob critério conservador), divergência financeira quantificada (63 de 562 registros, R$282,57 a R$2,26M).
- **9 regras de negócio fechadas e validadas contra o banco** (`docs/business_rule.md`), todas com números re-conferidos por script automatizado:
  1. Normalização de grafia de status (case/acento).
  2. `Cancelado` e `Distrato` tratados como a mesma categoria (`distrato`) — decisão baseada em evidência, sem separação estatística encontrada.
  3. Em conflito entre `status_venda` e `data_distrato`, a data tem precedência.
  4. "Venda ativa" = não distratada, aplicando as regras 1 e 3.
  5. "Total ofertado" (denominador da velocidade de vendas) = todas as unidades cadastradas, mesmo em empreendimentos "Suspenso".
  6. Cliente duplicado = nome + cidade + data_cadastro idênticos (critério conservador; resultado: 0 duplicados nesta base — e-mail é sintético, não serve de chave).
  7. Tolerância de divergência financeira = R$1,00 absoluto (avaliou-se tolerância relativa de 1%, mas descartada — não havia zona cinzenta nos dados).
  8. Senha placeholder `trocar_no_setup` → hash SHA-256 de senha temporária documentada.
  9. Unidade distratada não retorna automaticamente a "disponível" — liberação é ação manual.

## 5. O que falta fazer (em ordem de prioridade, segundo o roadmap)

🔴 **Crítico — começar agora:**
- Bloco 3 do Dia 1 (setup): estrutura de pastas (`app/`, `core/`, `analytics/`, `nl_assistant/`), `core/db.py` (conexão SQLite + `run_query()`), `core/auth.py` (login com hash SHA-256, regra 8), `main.py` (tela de login).
- Bloco 4 do Dia 1 / Bloco 1 do Dia 2 (camada de escrita — o item mais observado da avaliação): `core/regras_negocio.py` aplicando as regras 1–4 e 9; fluxo "Registrar venda" (unidade disponível + cliente novo/existente, validação, transação atômica BEGIN/COMMIT); fluxo "Registrar distrato" (venda ativa → distrato → unidade vai para `distrato`, não `disponível`, conforme regra 9); bloqueio explícito de venda de unidade indisponível, com mensagem clara.

🟠 **Importante — Dia 2:**
- Camada analítica: as 4 perguntas de negócio (velocidade de vendas, risco de estouro de custo, clientes duplicados, divergência financeira), cada uma aplicando as regras já fechadas.
- Painel de qualidade de dado (mostrar os achados de `data_exploration.md` na tela, não só no README).

🔴 **Crítico — Dia 3 (sexta 04/09, entrega):**
- Assistente de linguagem natural: `nl_assistant/text_to_sql.py` (Groq + schema → SQL) e `nl_assistant/guardrails.py` (bloquear qualquer coisa que não seja SELECT), mostrando a SQL gerada na tela (rastreabilidade). Testar com pelo menos 5 perguntas, incluindo 2 fora do roteiro oficial.
- Testes ponta a ponta: rodar o app do zero, `tests/test_regras_negocio.py` com pelo menos os testes críticos (bloquear venda de unidade indisponível).
- README completo (objetivo, arquitetura, stack, instalação, execução, regras de negócio, tratamento de dados, premissas, métricas, limitações, funcionamento da IA, decisões importantes) — o rascunho atual só tem a introdução.
- Preparação da apresentação de 08/09 (simulação de perguntas do Yan).

🟡 **Não fazer agora (fora de escopo, risco de scope creep):** autenticação de produção (OAuth), deploy em nuvem, pipeline de ingestão, arquitetura de microsserviços — o roadmap já descarta tudo isso explicitamente.

## 6. Onde estão os arquivos de referência

- `docs/data_exploration.md` — achados da exploração de dados.
- `docs/business_rule.md` — as 9 regras de negócio formalizadas.
- `docs/decisions.md` — criado mas ainda vazio (destinado a log de decisões cronológico, se quiser manter separado do business_rule).
- `roadmap_teste_cambara.pdf` (raiz do repo) — plano detalhado dia a dia; também existe como documento no projeto Claude ("Projeto quadra").
- `context_avaliador_yan_lopes.md` e `context.md` — perfis de contexto no projeto Claude (não fazem parte do código-fonte).
- `data/cambara_teste_tecnico.db` — banco original, nunca editado manualmente.
