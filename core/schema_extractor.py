import sqlite3, json

class SchemaExtractor:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_schema_context(self) -> str:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        parts = []
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            cols = cur.fetchall()
            col_defs = ", ".join(f"{c[1]} ({c[2]})" for c in cols)
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cur.fetchone()[0]
            cur.execute(f"SELECT * FROM {table} LIMIT 3")
            samples = cur.fetchall()
            col_names = [c[1] for c in cols]
            sample_rows = [dict(zip(col_names, row)) for row in samples]
            parts.append(
                f"Table: {table} ({row_count} rows)\n"
                f"Columns: {col_defs}\n"
                f"Sample data: {json.dumps(sample_rows, default=str)}"
            )
        conn.close()
        return "\n\n".join(parts)

    def get_table_names(self) -> list:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        return tables

    def execute_query(self, sql: str) -> tuple:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
        return columns, rows

    def validate_sql(self, sql: str) -> tuple:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(f"EXPLAIN QUERY PLAN {sql}")
            conn.close()
            return True, None
        except Exception as e:
            return False, str(e)
