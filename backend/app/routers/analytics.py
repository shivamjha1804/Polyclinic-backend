from fastapi import APIRouter, Depends
from app.deps import require_permission
from app.agents.followup import get_overdue_followups, get_overdue_referrals
from pydantic import BaseModel
from app.agents.analytics import ask_analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])

class AnalyticsQuestion(BaseModel):
    question: str

@router.get("/followups")
async def followups_worklist(user: dict = Depends(require_permission("followups", "view"))):
    return{
        "overdue_followups" : get_overdue_followups(),
        "overdue_referrals" : get_overdue_referrals()
    }

@router.post("/ask")
async def ask(payload: AnalyticsQuestion, user: dict = Depends(require_permission("analytics", "view"))):
    return ask_analytics(payload.question)

