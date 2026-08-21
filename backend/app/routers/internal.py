from fastapi import APIRouter, Header, HTTPException
from app.config import settings
from app.agents.followup import get_overdue_referrals, get_overdue_followups
from app.services.audit import log_action
from datetime import datetime, timezone
from app.db.client import supabase_admin

router = APIRouter(prefix="/internal", tags=["internal"])

@router.post("/followup-scan")
async def followup_scan(x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(403, "Invalid internal token")

    followups = get_overdue_followups()
    referrals = get_overdue_referrals()

    log_action(
        actor_id=None,
        actor_role=None,
        action="followup_scan",
        resource_type="system",
        resource_id=None,
        metadata={
            "overdue_followups_count": len(followups),
            "overdue_referrals_count": len(referrals),
        },
    )

    return {
        "overdue_followups_count": len(followups),
        "overdue_referrals_count": len(referrals),
    }

@router.post("/hold-expiry-scan")
async def hold_expiry_scan(x_internal_token: str = Header(...)):
    if x_internal_token != settings.INTERNAL_TOKEN:
        raise HTTPException(403, "Invalid internal token")

    now = datetime.now(timezone.utc).isoformat()
    expired = (
        supabase_admin.table("appointments")
        .select("id")
        .eq("status", "pending_payment")
        .lt("hold_expires_at", now)
        .execute()
    ).data

    for row in expired:
        supabase_admin.table("appointments").update(
            {"status": "cancelled", "hold_expires_at": None}
        ).eq("id", row["id"]).execute()

    return {"expired_count": len(expired)}    