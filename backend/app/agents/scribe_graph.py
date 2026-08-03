from typing import TypedDict
import json
from app.services.llm import complete_json
from app.config import settings
from pydantic import ValidationError
from app.schemas.soap import SoapNote
from langgraph.graph import StateGraph, END


class ScribeState(TypedDict):
    consultation_id: str
    patient_id: str
    transcript: str
    entities: dict
    soap_draft: dict
    validation_flags: list[dict]
    revision_count: int

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


builder = StateGraph(ScribeState)
builder.add_node("extract_entities", extract_entities)
builder.add_node("draft_soap", draft_soap, dependencies=["extract_entities"])
builder.add_node("validate", validate, dependencies=["draft_soap"])

builder.set_entry_point("extract_entities")
builder.add_edge("extract_entities", "draft_soap")
builder.add_edge("draft_soap", "validate")
builder.add_edge("validate", END)

graph = builder.compile()