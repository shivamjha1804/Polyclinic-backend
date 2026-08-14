import psycopg
from app.db.client import supabase_admin
from app.services.embeddings import embed_query
from app.config import settings


def hybrid_search(question: str, patient_id: str, match_count: int = 8) -> list[dict]:
    q_emb = embed_query(question)
    result = supabase_admin.rpc("hybrid_search", {
        "q_text": question,
        "q_emb": q_emb,
        "pid": patient_id,
        "match_count": match_count
    }).execute()
    return result.data


def vector_only_search(question: str, patient_id: str, match_count: int = 8) -> list[dict]:
    q_emb = embed_query(question)
    conn = psycopg.connect(settings.SUPABASE_DB_URL)
    cur = conn.cursor()
    cur.execute("""
        select id, section, content
        from record_chunks
        where patient_id = %s
        order by embedding <=> %s::vector
        limit %s
    """, (patient_id, q_emb, match_count))

    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "section": r[1], "content": r[2]} for r in rows]


def lexical_only_search(question: str, patient_id: str, match_count: int = 8) -> list[dict]:
    conn = psycopg.connect(settings.SUPABASE_DB_URL)
    cur = conn.cursor()
    cur.execute("""
        select id, section, content
        from record_chunks
        where patient_id = %s and content_tsv @@ plainto_tsquery('english', %s)
        order by ts_rank(content_tsv, plainto_tsquery('english', %s)) desc
        limit %s
    """, (patient_id, question, question, match_count))

    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "section": r[1], "content": r[2]} for r in rows]
