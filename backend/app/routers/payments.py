import hmac
import hashlib
import razorpay
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import current_user
from app.db.client import supabase_admin
from app.config import settings
from app.services.realtime import manager
from app.services.email import send_email

router = APIRouter(prefix="/payments", tags=["payments"])

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# Flat consultation fee for the prototype -- a real system would price this
# per doctor/specialty, but nothing in our schema carries a fee yet.
CONSULTATION_FEE_PAISE = 50000  # INR 500.00


class CreateOrder(BaseModel):
    appointment_id: str


@router.post("/create-order")
async def create_order(payload: CreateOrder, user: dict = Depends(current_user)):
    appointment = (
        supabase_admin.table("appointments")
        .select("*").eq("id", payload.appointment_id).single().execute()
    ).data

    if appointment is None:
        raise HTTPException(404, "Appointment not found")
    if appointment["patient_id"] != user["id"]:
        raise HTTPException(403, "Not your appointment")
    if appointment["status"] != "pending_payment":
        raise HTTPException(400, "This appointment is not awaiting payment")

    order = client.order.create({
        "amount": CONSULTATION_FEE_PAISE,
        "currency": "INR",
        "receipt": payload.appointment_id,
    })

    payment_row = supabase_admin.table("payments").insert({
        "appointment_id": payload.appointment_id,
        "patient_id": user["id"],
        "razorpay_order_id": order["id"],
        "amount": CONSULTATION_FEE_PAISE / 100,
        "currency": "INR",
        "status": "created",
    }).execute()

    return {
        "order_id": order["id"],
        "amount": CONSULTATION_FEE_PAISE,
        "currency": "INR",
        "key_id": settings.RAZORPAY_KEY_ID,
        "payment_row_id": payment_row.data[0]["id"],
    }


class VerifyPayment(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/verify")
async def verify_payment(payload: VerifyPayment, user: dict = Depends(current_user)):
    payment_row = (
        supabase_admin.table("payments")
        .select("*").eq("razorpay_order_id", payload.razorpay_order_id).single().execute()
    ).data

    if payment_row is None:
        raise HTTPException(404, "No matching order found")
    if payment_row["patient_id"] != user["id"]:
        raise HTTPException(403, "Not your payment")

    message = f"{payload.razorpay_order_id}|{payload.razorpay_payment_id}"
    expected_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, payload.razorpay_signature):
        supabase_admin.table("payments").update({"status": "failed"}).eq(
            "id", payment_row["id"]
        ).execute()
        raise HTTPException(400, "Signature verification failed")

    supabase_admin.table("payments").update({
        "status": "paid",
        "razorpay_payment_id": payload.razorpay_payment_id,
    }).eq("id", payment_row["id"]).execute()

    supabase_admin.table("appointments").update({
        "status": "booked",
        "hold_expires_at": None,
    }).eq("id", payment_row["appointment_id"]).execute()

    await manager.notify(user["id"], {
        "type": "payment_confirmed",
        "appointment_id": payment_row["appointment_id"],
        "amount": payment_row["amount"],
    })

    patient_email = supabase_admin.auth.admin.get_user_by_id(user["id"]).user.email
    send_email(
        to=patient_email,
        subject="Booking confirmed",
        html=(
            f"<p>Your appointment is confirmed.</p>"
            f"<p>Amount paid: &#8377;{payment_row['amount']}</p>"
            f"<p>Payment ID: {payload.razorpay_payment_id}</p>"
        ),
    )

    return {"status": "paid"}
