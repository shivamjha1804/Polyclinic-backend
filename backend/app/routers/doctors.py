from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import current_user
from app.db.client import supabase_admin
from app.services.llm import complete_text
from app.config import settings

router = APIRouter(prefix="/doctors", tags=["doctors"])

@router.get("")
async def list_doctors(specialty: str | None = None, user: dict = Depends(current_user)):
    query = supabase_admin.table("profiles").select(
        "id, full_name, specialty, bio, years_experience, qualifications"
    ).eq("role", "doctor")

    if specialty:
        query = query.eq("specialty", specialty)

    return query.execute().data

class DoctorQuestion(BaseModel):
    question: str


DOCTOR_QA_PROMPT = """You are answering a patient's question about a specific doctor, using only
the doctor's profile information provided. If the profile doesn't contain enough information to
answer, say so honestly rather than guessing."""

@router.post("/{doctor_id}/ask")
async def ask_about_doctor(doctor_id: str, payload: DoctorQuestion, user: dict = Depends(current_user)):
    doctor = (
        supabase_admin.table("profiles")
        .select("full_name, specialty, bio, years_experience, qualifications")
        .eq("id", doctor_id).eq("role", "doctor").single().execute()
    ).data

    if doctor is None:
        raise HTTPException(404, "Doctor not found")

    profile_text = (
        f"Name: {doctor['full_name']}\n"
        f"Specialty: {doctor['specialty']}\n"
        f"Qualifications: {doctor['qualifications']}\n"
        f"Years of experience: {doctor['years_experience']}\n"
        f"Bio: {doctor['bio']}"
    )
    user_message = f"Doctor profile:\n{profile_text}\n\nQuestion: {payload.question}"

    answer = complete_text(DOCTOR_QA_PROMPT, user_message, model=settings.MODEL_FAST)
    return {"answer": answer}