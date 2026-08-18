from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import current_user
from app.db.client import supabase_admin
from app.services.scheduling import get_available_slots

router = APIRouter(prefix="/appointments", tags=["appointments"])

@router.get("/slots")
async def slots(doctor_id: str, date: str, user: dict = Depends(current_user)):
    return get_available_slots(doctor_id, date)

class AppointmentCreate(BaseModel):
    doctor_id: str
    starts_at: str
    reason: str | None = None

class ScheduleUpdate(BaseModel):
    working_hours_start: str
    working_hours_end: str
    slot_duration_minutes: int = 30


@router.post("")
async def create_appointment(payload: AppointmentCreate, user: dict =Depends(current_user)):
    if user["role"] != "patient":
        raise HTTPException(403, "Only patients can book appointments")

    doctor = (
        supabase_admin.table("profiles")
        .select("slot_duration_minutes")
        .eq("id", payload.doctor_id)
        .single()
        .execute()
    ).data

    if doctor is None:
        raise HTTPException(404, "Doctor not found")

    slot_minutes = doctor["slot_duration_minutes"] or 30
    starts_at = datetime.fromisoformat(payload.starts_at)
    ends_at = starts_at + timedelta(minutes=slot_minutes)

    conflict = (
        supabase_admin.table("appointments")
        .select("id")
        .eq("doctor_id", payload.doctor_id)
        .eq("starts_at", starts_at.isoformat())
        .in_("status", ["booked", "pending_payment"])
        .execute()
    ).data

    if conflict:
        raise HTTPException(409, "This slot was just taken")

    result = supabase_admin.table("appointments").insert({
        "patient_id": user["id"],
        "doctor_id": payload.doctor_id,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "status": "booked",
        "reason": payload.reason
    }).execute()

    return result.data[0]


@router.delete("/{appointment_id}")
async def cancel_appointment(appointment_id: str, user: dict = Depends(current_user)):
    appintment = (
        supabase_admin.table("appointments")
        .select("*")
        .eq("id", appointment_id)
        .single()
        .execute()
    ).data

    if appintment is None:
        raise HTTPException(404, "Appointment not found")

    if user["id"] not in (appintment["patient_id"], appintment["doctor_id"]) and user["role"] != "owner":
        raise HTTPException(403, "Not your appointment")

    (
        supabase_admin.table("appointments")
        .update({"status": "cancelled"})
        .eq("id", appointment_id)
        .execute()
    )

    return {"status": "cancelled"}

@router.get("/mine")
async def my_appointment(user: dict = Depends(current_user)):
    now = datetime.now(timezone.utc).isoformat()
    column = "patient_id" if user["role"] == "patient" else "doctor_id"

    result = (
        supabase_admin.table("appointments")
        .select("*")
        .eq(column, user["id"])
        .gte("starts_at", now)
        .order("starts_at")
        .execute()
    )

    return result.data

@router.patch("/my-schedule")
async def update_my_schedule(payload: ScheduleUpdate, user: dict = Depends(current_user)):
    if user["role"] != "doctor":
        raise HTTPException(403, "Only doctors can set their own schedule")

    result = (
        supabase_admin.table("profiles")
        .update({
            "working_hours_start": payload.working_hours_start,
            "working_hours_end": payload.working_hours_end,
            "slot_duration_minutes": payload.slot_duration_minutes
        })
        .eq("id", user["id"])
        .execute()
    )
    return result.data[0]