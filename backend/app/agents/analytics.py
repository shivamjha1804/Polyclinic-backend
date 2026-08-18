import re
import json
import psycopg
from datetime import datetime, timezone
from app.services.llm import complete_json
from app.config import settings

SCHEMA_DESCRIPTION = """
You have access to these three read-only views:

v_appointments_by_doctor_month(doctor_id, doctor_name, month, total_appointments, completed, cancelled, no_show)
  -- appointment counts per doctor per month

v_noshow_rate(doctor_id, doctor_name, month, total_appointments, no_shows, noshow_rate_pct)
  -- no-show rate per doctor per month

v_lab_severity_summary(month, analyte, severity, result_count)
  -- lab result counts by analyte and severity per month
"""


def _build_prompt() -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""You are a Postgres analyst. Today's date is {today} -- use this, not your training
data, for any relative time expression ("last month", "this month", "this year").
You can ONLY query these views:
{SCHEMA_DESCRIPTION}

Rules:
- Only use the views listed above. Never reference any other table.
- Write a single SELECT query, nothing else.
- The `month` column in every view is a full timestamp (from date_trunc('month', ...)), not just a
  year-month string. Always write month literals as a full date, e.g. '2026-08-01', never '2026-08'.
- For comparative questions ("why did X change", "how does this month compare"), write a query
  that compares the relevant metric across time periods so the difference can be reported --
  never guess a cause without the data to support it.
- If the question cannot be answered using only these views, respond with can_answer: false and
  a short explanation instead of guessing or improvising a join.
- Respond only in JSON: {{"can_answer": bool, "sql": string or null, "explanation": string}}
"""


FORBIDDEN_PATTERN = re.compile(r"\b(insert|update|delete|drop|alter|grant|copy|truncate)\b", re.IGNORECASE)


def generate_sql(question: str) -> dict:
    raw = complete_json(_build_prompt(), question, model=settings.MODEL_PRIMARY)
    return json.loads(raw)

def run_readonly_query(sql: str) -> list[dict]:
    if FORBIDDEN_PATTERN.search(sql):
        raise ValueError("Query contains a forbidden keyword")

    conn = psycopg.connect(settings.ANALYTICS_DB_URL)
    conn.execute("SET statement_timeout = '5s'")
    cur = conn.cursor()
    cur.execute(sql)
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return rows

def ask_analytics(question: str) -> dict:
    plan = generate_sql(question)

    if not plan.get("can_answer"):
        return {"can_answer": False, "sql": None, "rows": None, "explanation": plan.get("explanation")}

    sql = plan["sql"]
    try:
        rows = run_readonly_query(sql)

    except Exception as e:
        return{"can_answer": False, "sql": sql, "rows": None, "explanation": f"Query failed: {e}"}

    return {"can_answer": True, "sql": sql, "rows": rows, "explanation": plan.get("explanation")}