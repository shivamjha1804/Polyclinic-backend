from fastapi import APIRouter, Header, HTTPException
from app.config import settings
from app.agents.followup import get_overdue_referrals, get_overdue_followups
from app.services.audit import log_action

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