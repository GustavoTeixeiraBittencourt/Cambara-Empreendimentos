import os
import shutil
import sys
import tempfile

# Garante que 'app/' está no path ao rodar pytest a partir da raiz do projeto,
# espelhando o comportamento do Streamlit (que adiciona app/ automaticamente).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

# Testes de escrita (registrar_venda/registrar_distrato) alteram dados de
# verdade. Antes desta correção, eles rodavam direto contra
# data/cambara_teste_tecnico.db — o mesmo banco usado na demonstração — e só
# ficavam seguros porque cada teste fazia sua própria limpeza manual; qualquer
# falha no meio de um teste deixaria lixo permanente nesse banco. Copiamos o
# banco para um arquivo temporário e apontamos DB_PATH para ele ANTES de
# qualquer módulo importar core.db (que lê DB_PATH uma única vez, na
# importação) — a suíte inteira passa a rodar sobre uma cópia descartável.
_DB_ORIGINAL = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "data", "cambara_teste_tecnico.db")
)
_TMP_DIR = tempfile.mkdtemp(prefix="cambara_test_db_")
_DB_TESTE = os.path.join(_TMP_DIR, "cambara_teste_tecnico.db")
shutil.copyfile(_DB_ORIGINAL, _DB_TESTE)
os.environ["DB_PATH"] = _DB_TESTE


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_DIR, ignore_errors=True)
