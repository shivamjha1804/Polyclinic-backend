from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import require_role
from app.db.client import supabase_admin
from app.services.storage import create_audio_upload_url
from app.services.asr import transcribe
from app.agents.scribe_graph import graph as scribe_graph
from langgraph.types import Command
from datetime import datetime, timezone
from app.services.audit import log_action

router = APIRouter(prefix="/consultations", tags=["consultations"])

class ConsultationCreate(BaseModel):
    appointment_id: str
    patient_id: str

class ReviewDecision(BaseModel):
    decision: str
    feedback: str | None = None
    edited_note: dict | None = None

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

    config = {"configurable" : {"thread_id" : consultation_id}}
    result = scribe_graph.invoke({"transcript" : transcript, "revision_count" : 0}, config= config)

    supabase_admin.table("consultations").update({
        "transcript" : transcript,
        "soap_note" : result["soap_draft"],
        "validation_flags" : result["validation_flags"],
        "status" : "drafted"
    }).eq("id", consultation_id).execute()

    return {"soap_draft" : result["soap_draft"], "validation_flags" : result["validation_flags"]}

@router.post("/{consultation_id}/review")
async def review_consultation(consultation_id: str, payload: ReviewDecision, user: dict = Depends(require_role("doctor"))):
    consultation = (
        supabase_admin.table("consultations")
        .select("*").eq("id", consultation_id).single().execute()
    ).data

    if consultation is None:
        raise HTTPException(404, "Consultation not found")
    if consultation["doctor_id"] != user["id"]:
        raise HTTPException(403, "You are not the doctor for this consultation")

    resume_payload = {"decision" : payload.decision}
    if payload.feedback is not None:
        resume_payload["feedback"] = payload.feedback
    if payload.edited_note is not None:
        resume_payload["edited_note"] = payload.edited_note

    config = {"configurable" : {"thread_id" : consultation_id}}
    result = scribe_graph.invoke(Command(resume=resume_payload), config=config)

    finished = "__interrupt__" not in result

    supabase_admin.table("consultations").update({
        "soap_note" : result["soap_draft"],
        "validation_flags" : result["validation_flags"],
        "revision_count" : result["revision_count"],
        "status": "in_review" if finished else "drafted",
    }).eq("id", consultation_id).execute()

    return{
        "finished" : finished,
        "soap_draft" : result["soap_draft"],
        "validation_flags" : result["validation_flags"]
    }


@router.post("/{consultation_id}/sign")
async def sign_consultation(consultation_id: str, user: dict = Depends(require_role("doctor"))):
    consultation = (
        supabase_admin.table("consultations")
        .select("*").eq("id", consultation_id).single().execute()
    ).data

    if consultation is None:
        raise HTTPException(404, "Consultation not found")

    if consultation["doctor_id"] != user["id"]:
        raise HTTPException(403, "You are not the doctor for this consultation")

    if consultation["signed_at"] is not None:
        raise HTTPException(400, "Consultation already signed")

    if consultation["soap_note"] is None:
        raise HTTPException(400, "No SOAP note to sign yet")

    if consultation["audio_path"]:
        supabase_admin.storage.from_("audio").remove([consultation["audio_path"]])

    supabase_admin.table("consultations").update({
        "status": "signed",
        "signed_at": datetime.now(timezone.utc).isoformat(),
        "audio_path": None,
    }).eq("id", consultation_id).execute()

    log_action(
        actor_id= user["id"],
        actor_role=user["role"],
        action="note_signed",
        resource_type="consultation",
        resource_id=consultation_id
    )

    return {"status": "signed"}