from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import current_user
from app.db.client import supabase_admin
import requests
from app.services.records import extract_text
from app.services.embeddings import chunk_document, embed_documents
from app.services.llm import complete_text
from app.config import settings

router = APIRouter(prefix="/records", tags=["records"])

RECORDS_BUCKET = "records"

class RecordCreate(BaseModel):
    patient_id: str
    title: str
    doc_type: str

class RecordIngest(BaseModel):
    record_id: str


SUMMARY_PROMPT = "You are summarizing a medical report in 2-3 sentences for a doctor's quick reference."

@router.post("/upload-url")
async def get_record_upload_url(payload: RecordCreate, user: dict = Depends(current_user)):
    if user["role"] == "patient" and user["id"] != payload.patient_id:
        raise HTTPException(403, "You can only upload yourt own records")

    result = supabase_admin.table("medical_records").insert({
        "patient_id": payload.patient_id,
        "title": payload.title,
        "doc_type": payload.doc_type
    }).execute()

    record = result.data[0]

    path = f"{record['id']}/document"
    signed = supabase_admin.storage.from_(RECORDS_BUCKET).create_signed_upload_url(path)

    supabase_admin.table("medical_records").update({"file_path": path}).eq("id", record["id"]).execute()

    return {"record_id" : record["id"], "path" : path, "signed_url" : signed["signed_url"], "token" : signed["token"]}


@router.post("/ingest")
async def ingest_record(payload: RecordIngest, user: dict = Depends(current_user)):
    record= (
        supabase_admin.table("medical_records")
        .select("*").eq("id", payload.record_id).single().execute()
    ).data

    if record is None:
        raise HTTPException(404, "Record not found")

    if user["role"] == "patient" and user["id"] != record["patient_id"]:
        raise HTTPException(403, "You can only ingest your own records")

    signed = supabase_admin.storage.from_(RECORDS_BUCKET).create_signed_url(record["file_path"], 60)
    raw_bytes = requests.get(signed["signedURL"]).content
    text = extract_text(raw_bytes)

    chunks = chunk_document(text)
    content = [c["content"] for c in chunks]
    embeddings = embed_documents(content)

    rows = [
        {
            "record_id": record["id"],
            "patient_id": record["patient_id"],
            "section": chunk["section"],
            "content": chunk["content"],
            "embedding": embedding,
            "chunk_index": i,
        }
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    supabase_admin.table("record_chunks").insert(rows).execute()

    summary = complete_text(SUMMARY_PROMPT, text[:4000], model=settings.MODEL_FAST)
    supabase_admin.table("medical_records").update({"summary": summary}).eq("id", record["id"]).execute()

    return {"record_id": record["id"], "chunks_created": len(rows)}

@router.get("")
async def list_records(patient_id: str, user: dict = Depends(current_user)):
    if user["role"] == "patient" and user["id"] != patient_id:
        raise HTTPException(403, "You can only view your own records")

    result = (
        supabase_admin.table("medical_records")
        .select("*").eq("patient_id", patient_id).order("recorded_at", desc=True)
        .execute()
    )
    return result.data

@router.get("/{record_id}")
async def get_record(record_id : str, user : dict = Depends(current_user)):
    record = (
        supabase_admin.table("medical_records")
        .select("*").eq("id", record_id).single().execute()
    ).data

    if record is None:
        raise HTTPException(404, "Record not found")

    if user["role"] == "patient" and user["id"] != record["patient_id"]:
        raise HTTPException(403, "You can only view your own records")

    view_url = None

    if record["file_path"]:
        signed = supabase_admin.storage.from_(RECORDS_BUCKET).create_signed_url(record["file_path"], 300)
        view_url = signed["signedURL"]

    return {**record, "view_url" : view_url}