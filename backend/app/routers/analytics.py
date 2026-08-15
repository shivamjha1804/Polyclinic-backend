from fastapi import APIRouter, Depends
from app.deps import require_role
from app.agents.followup import get_overdue_followups, get_overdue_referrals

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/followups")
async def followups_worklist(user: dict = Depends(require_role("doctor", "owner"))):
    return{
        "overdue_followups" : get_overdue_followups(),
        "overdue_referrals" : get_overdue_referrals()
    }

