# file: app/services/customers_service.py

import duckdb
import re
from pathlib import Path

# ===========================================
# Inicialização persistente DuckDB
# ===========================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PARQUET_PATH = BASE_DIR / "data" / "parceiros.parquet"

# Instância única do DuckDB (persistente)
duckdb_conn = duckdb.connect(database=":memory:")

# Registrando o parquet como tabela virtual
duckdb_conn.execute(f"""
    CREATE VIEW clientes AS
    SELECT 
        "CNPJ / CPF" AS cnpj,
        "Nome Parceiro" AS nome,
        "Nome (Cidade)" AS cidade,
        "UF" AS uf
    FROM parquet_scan('{PARQUET_PATH.as_posix()}');
""")

print(f"[DuckDB] Base clientes carregada em memória: {PARQUET_PATH}")


# ===========================================
# Funções auxiliares
# ===========================================
def _normalize_cnpj(value: str) -> str:
    """Remove qualquer caractere que não seja número."""
    return re.sub(r"\D", "", value or "")


# ===========================================
# Função principal
# ===========================================
def get_customer_by_cnpj(cnpj_raw: str):
    cnpj = _normalize_cnpj(cnpj_raw)

    if not cnpj:
        return {"found": False}

    query = """
        SELECT cnpj, nome, cidade, uf
        FROM clientes
        WHERE regexp_replace(cnpj, '[^0-9]', '', 'g') = ?
        LIMIT 1;
    """

    result = duckdb_conn.execute(query, [cnpj]).fetchone()

    if not result:
        return {"found": False}

    return {
        "found": True,
        "customer_name": result[1],
        "customer_city": result[2],
        "customer_state": result[3],
    }
