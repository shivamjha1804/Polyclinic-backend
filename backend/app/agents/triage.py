from app.services.llm import complete_text
from app.config import settings
from app.db.client import supabase_admin


def triage_severity(analyte: str, value: float, ref_low: float, ref_high: float) -> str:
    if ref_low <= value <= ref_high:
        return "normal"

    range_width = ref_high - ref_low
    if range_width <= 0:
        return "abnormal"  # malformed range, can't compute deviation -- fail safe, don't guess critical

    if value < ref_low:
        deviation = (ref_low - value) / range_width
    else:
        deviation = (value - ref_high) / range_width

    if deviation >= 0.5:
        return "critical"
    return "abnormal"


def generate_llm_context(patient_id: str, analyte: str, value: float, unit: str) -> str:
    prior = (
        supabase_admin.table("lab_results")
        .select("value, created_at")
        .eq("patient_id", patient_id)
        .eq("analyte", analyte)
        .order("created_at", desc=True)
        .limit(3)
        .execute()
    ).data

    if not prior:
        return ""

    prior_text = ", ".join(f"{p['value']}{unit} on {p['created_at']}" for p in prior)
    prompt = "You are a clinician's assistant writing a one-line contextual note comparing a new lab value to the patient's prior values. Be factual and brief, do not diagnose."
    user_message = f"New value: {value}{unit} for {analyte}. Prior values: {prior_text}"
    return complete_text(prompt, user_message, model=settings.MODEL_FAST, max_tokens=100)
