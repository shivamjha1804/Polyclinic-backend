from typing import TypedDict
import json
from app.services.llm import complete_json
from app.config import settings
from app.db.client import supabase_admin
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection

_checkpointer_conn = Connection.connect(settings.SUPABASE_DB_URL, autocommit=True, prepare_threshold=0)
checkpointer = PostgresSaver(_checkpointer_conn)
checkpointer.setup()

class IntakeState(TypedDict):
    messages: list[dict]
    suggested_specialty: str | None

def _get_available_specialties() -> list[str]:
    rows = supabase_admin.table("profiles").select("specialty").eq("role", "doctor").execute().data
    return sorted({r["specialty"] for r in rows if r["specialty"]})

INTAKE_PROMPT_TEMPLATE = """You are a friendly clinic intake assistant. A patient is describing their
symptoms. Have a brief, warm conversation to understand what's wrong, then suggest which medical
specialty they should see, chosen ONLY from this list: {specialties}.
Respond only in JSON: {{"reply": string, "suggested_specialty": string or null}}
Only set suggested_specialty once you have enough information -- ask a clarifying question first if needed."""

def converse(state: IntakeState) -> dict:
    specialties = _get_available_specialties()
    prompt = INTAKE_PROMPT_TEMPLATE.format(specialties=', '.join(specialties))

    conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in state["messages"])
    raw = complete_json(prompt, conversation_text, model=settings.MODEL_PRIMARY)
    result = json.loads(raw)

    new_messages = state["messages"] + [{"role": "assistant", "content": result["reply"]}]
    return {"messages": new_messages, "suggested_specialty": result.get("suggested_specialty")}


builder = StateGraph(IntakeState)
builder.add_node("converse", converse)
builder.set_entry_point("converse")
builder.add_edge("converse", END)

graph = builder.compile(checkpointer=checkpointer)