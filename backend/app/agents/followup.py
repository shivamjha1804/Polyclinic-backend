from app.config import settings
from app.services.llm import complete_json
import json
import psycopg


URGENCY_PROMPT = """You are triaging a patient's follow-up urgency based on their diagnoses.
Respond only in JSON: {"urgency_tier": "chronic" or "routine"}
"chronic" means the diagnosis list includes any ongoing condition requiring regular monitoring
(e.g. diabetes, hypertension, heart disease, chronic kidney disease, COPD, asthma, cancer under
treatment, autoimmune conditions, and similar).
"routine" means the diagnoses are acute/self-limited (e.g. sprains, minor infections, injuries)
with no chronic component."""

def _urgency_tier(diagnoses: list[str]) -> str:
    if not diagnoses:
        return "routine"
    user_message = f"Diagnoses: {json.dumps(diagnoses)}"
    raw = complete_json(URGENCY_PROMPT, user_message, model=settings.MODEL_FAST)
    return json.loads(raw).get("urgency_tier", "routine")


def get_overdue_followups() -> list[dict]:
    conn = psycopg.connect(settings.SUPABASE_DB_URL)
    cur = conn.cursor()
    cur.execute("""
        select c.id, c.patient_id, c.doctor_id, c.signed_at, c.follow_up_days,
               c.soap_note->'diagnosis' as diagnoses,
               extract(day from now() - (c.signed_at + (c.follow_up_days || ' days')::interval))::int as days_overdue
        from consultations c
        where c.status = 'signed'
          and c.follow_up_days is not null
          and c.signed_at + (c.follow_up_days || ' days')::interval < now()
          and not exists (
            select 1 from appointments a
            where a.patient_id = c.patient_id and a.starts_at > now()
          )
    """)
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()

    for row in rows:
        diagnoses = row["diagnoses"] or []
        row["urgency_tier"] = _urgency_tier(diagnoses)

    rows.sort(key=lambda r: (r["urgency_tier"] != "chronic", -r["days_overdue"]))
    return rows


def get_overdue_referrals() -> list[dict]:
    conn = psycopg.connect(settings.SUPABASE_DB_URL)
    cur = conn.cursor()
    cur.execute("""
        select id, patient_id, from_doctor, to_specialty, sent_at,
               extract(day from now() - sent_at)::int as days_since_sent
        from referrals
        where report_received_at is null
          and sent_at < now() - interval '30 days'
        order by days_since_sent desc
    """)
    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    conn.close()
    return rows