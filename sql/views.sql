-- ============================================================================
-- Views de leitura — normalizacao de status (regras 1, 2 e 3 de docs/business_rule.md)
--
-- Nao alteram nenhum dado das tabelas originais (unidades, vendas): sao objetos
-- somente-leitura derivados, criados via DROP VIEW IF EXISTS + CREATE VIEW (DDL
-- idempotente, nunca um UPDATE/DELETE sobre linha existente).
--
-- Aplicadas uma unica vez, via "python scripts/aplicar_views.py" (mesmo padrao
-- de scripts/setup_senhas.py) — ja rodado no banco entregue com o projeto. Nao
-- sao recriadas automaticamente a cada conexao (core/db.py fica so com
-- SELECT/INSERT/UPDATE do dia a dia); DDL e' um evento raro e deliberado, nao
-- algo para repetir silenciosamente em todo connect().
--
-- SQL puro, sem funcoes customizadas (UDF): funciona em qualquer cliente SQLite
-- (DB Browser, sqlite3 CLI, etc.), nao so atraves da aplicacao Python. Isso e
-- deliberado — o objetivo destas views e serem auditaveis por qualquer
-- ferramenta, nao so pela aplicacao.
--
-- Adendo de 03/09/2026 (ver docs/business_rule.md, regra 3): o rotulo canonico
-- de vendas.status_venda passou de "distrato" para "distratada" (par gramatical
-- de "ativa" — ambos adjetivos). unidades.status mantem "distrato" (regra 2,
-- inalterada — colunas conceitualmente distintas, sem exigencia de bater string).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- vw_vendas — status_venda normalizado (regras 1 + 3)
-- ----------------------------------------------------------------------------
-- vendas.status_venda nao tem valores acentuados nos dados atuais (conferido em
-- banco: ATIVA/Ativa/ativa/distrato/Distrato/Distratada), entao LOWER(TRIM(...))
-- ja e suficiente para a regra 1 aqui. A categoria "distrato"/"distratada"/
-- "cancelado" colapsa para "distratada" (regra 3); qualquer outro valor
-- normalizado e tratado como "ativa". data_distrato preenchida tem precedencia
-- sobre o texto do status (regra 3) — replica esta_distratada() do Python.
DROP VIEW IF EXISTS vw_vendas;
CREATE VIEW vw_vendas AS
WITH base AS (
    SELECT
        v.*,
        CASE
            WHEN v.data_distrato IS NOT NULL AND TRIM(v.data_distrato) <> '' THEN 1
            WHEN LOWER(TRIM(v.status_venda)) IN ('distrato', 'distratada', 'cancelado') THEN 1
            ELSE 0
        END AS _distratada
    FROM vendas v
)
SELECT
    id,
    unidade_id,
    cliente_id,
    data_venda,
    valor_venda,
    forma_pagamento,
    status_venda AS status_venda_original,
    data_distrato,
    CASE WHEN _distratada = 1 THEN 'distratada' ELSE 'ativa' END AS status_venda_normalizado,
    _distratada AS venda_distratada
FROM base;

-- ----------------------------------------------------------------------------
-- vw_unidades — status normalizado (regras 1 + 2)
-- ----------------------------------------------------------------------------
-- unidades.status TEM valor acentuado real na base ("Disponivel" com acento,
-- 314 linhas) — diferente de vendas.status_venda. Uma comparacao direta tipo
-- WHERE status = 'disponivel' sem tratar o acento perde ~2/3 dos casos (so
-- bateria com as 299 linhas ja escritas sem acento). A cadeia de REPLACE abaixo
-- cobre as vogais acentuadas + cedilha comuns em portugues antes do LOWER/TRIM —
-- mesmo resultado de normalizar_status() (Python) para os 11 valores brutos
-- hoje na base (conferido em banco em 03/09/2026), expressa em SQL puro para
-- nao depender de nenhuma funcao registrada pela aplicacao.
DROP VIEW IF EXISTS vw_unidades;
CREATE VIEW vw_unidades AS
WITH base AS (
    SELECT
        u.*,
        LOWER(TRIM(
            REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(u.status,
            'á','a'),'à','a'),'ã','a'),'â','a'),'é','e'),'ê','e'),'í','i'),'ó','o'),'ô','o'),'õ','o'),'ú','u'),'ç','c')
        )) AS _status_grafia
    FROM unidades u
)
SELECT
    id,
    empreendimento_id,
    identificador,
    tipo,
    area_privativa_m2,
    valor_tabela,
    status AS status_original,
    _status_grafia AS status_grafia_normalizada,
    CASE WHEN _status_grafia IN ('distrato', 'cancelado') THEN 'distrato' ELSE _status_grafia END AS status_categoria
FROM base;
