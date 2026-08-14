from app.services.llm import complete_json
from app.config import settings
import json

HALLUCINATION_PROMPT = """You are checking a clinical SOAP note for hallucinated facts -- claims not supported by the transcript.
Respond only in JSON: {"hallucinated_facts": [string], "hallucination_count": int}
A fact is hallucinated if it appears in the note but has no reasonable basis in the transcript."""


def diagnosis_recall_precision(predicted: list[str], expected: list[str]) -> tuple[float, float]:
    pred_set = {d.strip().lower() for d in predicted}
    exp_set = {d.strip().lower() for d in expected}

    if not exp_set:
        return (1.0, 1.0 if not pred_set else 0.0)

    true_positives = len(pred_set & exp_set)
    recall = true_positives/ len(exp_set)
    precision = true_positives/ len(pred_set) if pred_set else 0.0
    return (recall, precision)

def medication_f1(predicted: list[dict], expected: list[dict]) -> float:
    pred_names = {m["name"].strip().lower() for m in predicted}
    exp_names = {m["name"].strip().lower() for m in expected}

    if not exp_names and not pred_names:
        return 1.0

    if not pred_names or not exp_names:
        return 0.0

    tp = len(pred_names & exp_names)
    precision = tp / len(pred_names)
    recall = tp / len(exp_names)

    if precision + recall == 0:
        return 0.0

    return 2 * precision * recall / (precision + recall)

def dosage_exact_match(predicted : list[dict], expected: list[dict]) -> float:
    if not expected:
        return 1.0

    exp_by_name = {m["name"].strip().lower(): m["dosage"].strip().lower() for m in expected}
    matched = 0
    for m in predicted:
        name= m["name"].strip().lower()
        dosage = m.get("dosage", "").strip().lower()

        if name in exp_by_name and exp_by_name[name] == dosage:
            matched += 1

    return matched / len(expected)

def section_completeness(note: dict) -> float:
    sections = ["subjective", "objective", "assessment", "plan"]
    filled = sum(1 for s in sections if note.get(s, "").strip())
    return filled/len(sections)

def check_hallucinations(transcript: str, note: dict) -> dict:
    user_message = f"Transcript: \n{transcript}\n\nSOAP note:\n{json.dumps(note)}"
    raw = complete_json(HALLUCINATION_PROMPT, user_message, model=settings.MODEL_PRIMARY)
    return json.loads(raw)