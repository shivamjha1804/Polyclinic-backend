from app.db.client import supabase_admin
from app.services.embeddings import embed_query

def hybrid_search(question: str, patient_id: str, match_count: int = 8) -> list[dict]:
    q_emb = embed_query(question)
    result = supabase_admin.rpc("hybrid_search", {
        "q_text": question,
        "q_emb": q_emb,
        "pid": patient_id,
        "match_count": match_count
    }).execute()
    return result.data

