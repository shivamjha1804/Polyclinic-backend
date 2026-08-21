import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.deps import current_user
from app.agents.intake_graph import graph as intake_graph

router = APIRouter(prefix="/intake", tags=["intake"])

class IntakeMessage(BaseModel):
    session_id: str | None = None
    message: str

@router.post("/chat")
async def intake_chat(payload: IntakeMessage, user: dict = Depends(current_user)):
    session_id = payload.session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    state = intake_graph.get_state(config)
    existing_messages = state.values.get("messages", []) if state.values else []

    new_messages = existing_messages + [{"role": "user", "content": payload.message}]
    result = intake_graph.invoke({"messages": new_messages}, config=config)

    return {
        "session_id": session_id,
        "reply": result["messages"][-1]["content"],
        "suggested_specialty": result.get("suggested_specialty")
    }