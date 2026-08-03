from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import require_role
from app.db.client import supabase_admin
from app.services.storage import create_audio_upload_url
from app.services.asr import transcribe

router = APIRouter(prefix="/consultations", tags=["consultations"])

class ConsultationCreate(BaseModel):
    appointment_id: str
    patient_id: str

@router.post("")
async def create_consultation(payload: ConsultationCreate, user: dict = Depends(require_role("doctor"))):
    result = supabase_admin.table("consultations").insert({
        "appointment_id" : payload.appointment_id,
        "patient_id" : payload.patient_id,
        "doctor_id" : user["id"],
    }).execute()
    return result.data[0]

@router.post("/{consultation_id}/audio-url")
async def get_audio_upload_url(consultation_id: str, user: dict = Depends(require_role("doctor"))):
    consultation = (
        supabase_admin.table("consultations")
        .select("*").eq("id", consultation_id).single().execute()
    ).data

    if consultation is None:
        raise HTTPException(404, "Consultation not found")

    if consultation["doctor_id"] != user["id"]:
        raise HTTPException(403, "You are not the doctor for this consultation")

    result = create_audio_upload_url(consultation_id)
    supabase_admin.table("consultations").update({"audio_path": result["path"]}).eq("id", consultation_id).execute()
    return result

@router.post("/{consultation_id}/transcribe")
async def transcribe_consultation(consultation_id: str, user: dict = Depends(require_role("doctor"))):
    consultation = (
        supabase_admin.table("consultations")
        .select("*").eq("id", consultation_id).single().execute()
    ).data

    if consultation is None:
        raise HTTPException(404, "Consultation not found")

    if consultation["doctor_id"] != user["id"]:
        raise HTTPException(403, "You are not the doctor for this consultation")

    if consultation["audio_path"] is None:
        raise HTTPException(400, "No audio uploaded yet")

    if consultation["transcript"] is not None:
        raise HTTPException(400, "Consultation has already been transcribed")

    signed = supabase_admin.storage.from_("audio").create_signed_url(consultation["audio_path"], 60)
    transcript = transcribe(signed["signedURL"])

    supabase_admin.table("consultations").update({
        "transcript" : transcript,
        "status" : "transcribed"
    }).eq("id", consultation_id).execute()

    return {"transcript" : transcript}
