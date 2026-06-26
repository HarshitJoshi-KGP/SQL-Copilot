"""
SQL Copilot core — LLM-powered SQL generation with self-correction loop.
Uses Groq (free) with llama-3.1-70b.
"""
import os, re
from dotenv import load_dotenv
from groq import Groq
from .schema_extractor import SchemaExtractor

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an expert SQL assistant. You write precise, correct SQLite queries.

Rules:
- Return ONLY the SQL query, no explanation, no markdown backticks, no preamble
- Use only tables and columns that exist in the provided schema
- Always use proper SQLite syntax
- For date operations use SQLite date functions: date(), strftime()
- Never use LIMIT unless asked
- Always alias columns for clarity"""

FIX_PROMPT = """The following SQLite query failed with this error:

ERROR: {error}

ORIGINAL SQL:
{sql}

DATABASE SCHEMA:
{schema}

Fix the SQL query. Return ONLY the corrected SQL, nothing else."""

EXPLAIN_PROMPT = """Given this question: "{question}"
And this SQL query: {sql}
And this result (first 5 rows): {result_preview}

Write a clear 2-3 sentence plain English explanation of what the query found.
Be specific with numbers. Do not mention SQL."""

FOLLOWUP_PROMPT = """Given the research question: "{question}"
And the result summary: {result_preview}

Suggest 3 natural follow-up questions the user might want to ask next.
Return as a JSON array of strings: ["question1", "question2", "question3"]
Return ONLY the JSON array, nothing else."""


class SQLCopilot:
    def __init__(self, db_path: str, groq_api_key: str = None):
        self.db = SchemaExtractor(db_path)

        api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GROQ_API_KEY", None)
            except Exception:
                pass
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing.")

        self.client = Groq(api_key=api_key)

        # ADD THESE LINES
        print("API Key:", api_key[:10] + "...")
        print("Groq client initialized")

        self.max_retries = 3
        self.query_cache = {}

    def run(self, question: str) -> dict:
        print("=" * 60)
        print("Question:", question)

        cache_key = question.strip().lower()

        if cache_key in self.query_cache:
            print("Returned from cache")
            cached = self.query_cache[cache_key].copy()
            cached["from_cache"] = True
            return cached

        print("Loading schema...")
        schema = self.db.get_schema_context()

        print("Generating SQL...")
        sql = self._generate_sql(question, schema)
        print("Generated SQL:", sql)

        attempts = 0
        error = None

        for attempt in range(self.max_retries):
            attempts = attempt + 1

            print("Validating SQL...")
            is_valid, error = self.db.validate_sql(sql)

            print("Validation:", is_valid, error)

            if is_valid:
                try:
                    print("Executing SQL...")
                    columns, rows = self.db.execute_query(sql)

                    print("Rows returned:", len(rows))

                    result_preview = self._format_preview(columns, rows)
                    explanation = self._explain(question, sql, result_preview)
                    followups = self._suggest_followups(question, result_preview)
                    chart_type = self._pick_chart(columns, rows)

                    result = {
                        "sql": sql,
                        "columns": columns,
                        "rows": [list(r) for r in rows],
                        "row_count": len(rows),
                        "explanation": explanation,
                        "followups": followups,
                        "chart_type": chart_type,
                        "attempts": attempts,
                        "from_cache": False,
                        "error": None,
                    }

                    self.query_cache[cache_key] = result
                    return result

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    error = str(e)

            if attempt < self.max_retries - 1:
                print("Fixing SQL...")
                sql = self._fix_sql(sql, error, schema)

        return {
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "explanation": "Failed to generate a valid SQL query.",
            "followups": [],
            "chart_type": "table",
            "attempts": attempts,
            "from_cache": False,
            "error": error,
        }
    
    # ── LLM calls ─────────────────────────────────────────────────────────

    def _generate_sql(self, question: str, schema: str) -> str:
        prompt = f"""DATABASE SCHEMA:
{schema}

QUESTION: {question}

Write the SQLite query:"""
        print("Calling Groq API...")
        resp = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0,
            max_tokens=500,
        )
        return self._clean_sql(resp.choices[0].message.content)

    def _fix_sql(self, sql: str, error: str, schema: str) -> str:
        prompt = FIX_PROMPT.format(error=error, sql=sql, schema=schema)
        resp = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        return self._clean_sql(resp.choices[0].message.content)

    def _explain(self, question: str, sql: str, preview: str) -> str:
        prompt = EXPLAIN_PROMPT.format(question=question, sql=sql, result_preview=preview)
        resp = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()

    def _suggest_followups(self, question: str, preview: str) -> list:
        import json as _json
        prompt = FOLLOWUP_PROMPT.format(question=question, result_preview=preview)
        resp = self.client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=200,
        )
        try:
            text = resp.choices[0].message.content.strip()
            text = re.sub(r"```json|```", "", text).strip()
            return _json.loads(text)
        except Exception:
            return []

    # ── Helpers ───────────────────────────────────────────────────────────

    def _clean_sql(self, text: str) -> str:
        text = re.sub(r"```sql|```", "", text).strip()
        lines = [l for l in text.split("\n") if not l.strip().startswith("--")]
        return " ".join(lines).strip().rstrip(";")

    def _format_preview(self, columns: list, rows: list) -> str:
        if not rows:
            return "No results returned."
        preview = [dict(zip(columns, r)) for r in rows[:5]]
        return str(preview)

    def _pick_chart(self, columns: list, rows: list) -> str:
        if not rows or not columns:
            return "table"
        import re as _re
        date_cols    = [c for c in columns if _re.search(r"date|month|year|time|day", c, _re.I)]
        numeric_cols = []
        if rows:
            for i, col in enumerate(columns):
                try:
                    float(rows[0][i])
                    numeric_cols.append(col)
                except (TypeError, ValueError):
                    pass
        text_cols = [c for c in columns if c not in numeric_cols and c not in date_cols]

        if date_cols and numeric_cols:
            return "line"
        elif text_cols and len(numeric_cols) == 1 and len(rows) <= 20:
            return "bar"
        elif len(numeric_cols) >= 2:
            return "scatter"
        elif text_cols and len(numeric_cols) == 1 and len(rows) <= 8:
            return "pie"
        return "table"
