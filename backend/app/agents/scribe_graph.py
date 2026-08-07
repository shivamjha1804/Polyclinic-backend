from typing import TypedDict
import json
from app.services.llm import complete_json
from app.config import settings
from pydantic import ValidationError
from app.schemas.soap import SoapNote
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from langgraph.types import interrupt 

_checkpointer_conn = Connection.connect(settings.SUPABASE_DB_URL, autocommit=True, prepare_threshold=0)
checkpointer = PostgresSaver(_checkpointer_conn)
checkpointer.setup()

class ScribeState(TypedDict):
    consultation_id: str
    patient_id: str
    transcript: str
    entities: dict
    soap_draft: dict
    validation_flags: list[dict]
    revision_count: int
    doctor_decision: str
    doctor_feedback: str | None

ENTITY_EXTRACTION_PROMPT = """You are extracting structured clinical entities from a doctor-patient consultation transcript.
Respond only in JSON with this exact shape:
{"symptoms": [string], "diagnoses": [string], "medications": [{"name": string, "dosage": string}], "follow_up_days": int or null}
"""

def extract_entities(state: ScribeState) -> dict:
    raw = complete_json(
        system = ENTITY_EXTRACTION_PROMPT,
        user_message = state["transcript"],
        model = settings.MODEL_FAST,
        max_tokens = 2000
    )
    return {"entities": json.loads(raw)}


SOAP_DRAFTING_PROMPT = """You are a clinical scribe drafting a SOAP note from a consultation transcript and extracted entities.
Respond only in JSON with this exact shape:
{"subjective": string, "objective": string, "assessment": string, "plan": string,
 "diagnosis": [string], "medications": [{"name": string, "dosage": string, "frequency": string, "duration": string}],
 "follow_up": int or null}
"""

def draft_soap(state: ScribeState) -> dict:
    user_message = f"Transcript:\n{state['transcript']}\n\nExtracted entities:\n{json.dumps(state['entities'])}"

    for attempt in range(2):
        raw = complete_json(
            system = SOAP_DRAFTING_PROMPT,
            user_message = user_message,
            model = settings.MODEL_PRIMARY
        )
        try:
            note = SoapNote.model_validate_json(raw)
            return {"soap_draft" : note.model_dump()}
        except ValidationError as e:
            if attempt == 1:
                raise e
    raise RuntimeError("Failed to draft SOAP note after 2 attempts")


def validate(state: ScribeState) -> dict:
    note = state["soap_draft"]
    flags = []

    for section in ("subjective", "objective", "assessment", "plan"):
        if not note[section].strip():
            flags.append({"type": "empty_section", "section": section})

    if not note["diagnosis"]:
        flags.append({"type": "no_diagnosis"})

    return {"validation_flags": flags}

def doctor_review(state: ScribeState) -> dict:
    decision = interrupt({
        "soap_draft": state["soap_draft"],
        "validation_flags": state["validation_flags"]
    })
    return {
        "doctor_decision": decision.get("decision"),
        "doctor_feedback": decision.get("feedback"),
        "soap_draft": decision.get("edited_note", state["soap_draft"])
    }

REVISE_PROMPT = """You are revising a SOAP note based on doctor feedback.
Respond only in JSON with this exact shape:
{"subjective": string, "objective": string, "assessment": string, "plan": string,
 "diagnosis": [string], "medications": [{"name": string, "dosage": string, "frequency": string, "duration": string}],
 "follow_up": int or null}
"""

def revise(state: ScribeState) -> dict:
    user_message = f"Current note:\n{json.dumps(state['soap_draft'])}\n\nDoctor feedback:\n{state['doctor_feedback']}"

    for attempt in range(2):
        raw = complete_json(
            system = REVISE_PROMPT,
            user_message = user_message,
            model = settings.MODEL_PRIMARY
        )
        try:
            note = SoapNote.model_validate_json(raw)
            return {"soap_draft" : note.model_dump(), "revision_count" : state["revision_count"] + 1}
        except ValidationError as e:
            if attempt == 1:
                raise e

    raise RuntimeError("Failed to revise SOAP note after 2 attempts")

def commit(state: ScribeState) -> dict:
    return{}

def route_after_reivew(state: ScribeState) -> str:
    if state["doctor_decision"] == "approve":
        return  "commit"
    if state["revision_count"] >= 2:
        return "doctor_review"
    return "revise"

builder = StateGraph(ScribeState)
builder.add_node("extract_entities", extract_entities)
builder.add_node("draft_soap", draft_soap)
builder.add_node("validate", validate)
builder.add_node("doctor_review", doctor_review)
builder.add_node("revise", revise)
builder.add_node("commit", commit)

builder.set_entry_point("extract_entities")
builder.add_edge("extract_entities", "draft_soap")
builder.add_edge("draft_soap", "validate")
builder.add_edge("validate", "doctor_review")
builder.add_conditional_edges(
    "doctor_review",
    route_after_reivew,
    {"revise": "revise", "commit" : "commit", "doctor_review" : 'doctor_review'}
)
builder.add_edge("revise", "validate")
builder.add_edge("commit", END)

graph = builder.compile(checkpointer=checkpointer)