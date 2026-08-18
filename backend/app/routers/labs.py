from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import require_permission
from app.db.client import supabase_admin
from app.agents.triage import triage_severity, generate_llm_context

router = APIRouter(prefix="/labs", tags=["labs"])

class LabResultCreate(BaseModel):
    patient_id: str
    analyte: str
    value: float
    unit: str
    ref_low: float
    ref_high: float

@router.post("")
async def create_lab_result(payload: LabResultCreate, user: dict = Depends(require_permission("labs", "create"))):
    severity = triage_severity(payload.analyte, payload.value, payload.ref_low, payload.ref_high)
    llm_context = generate_llm_context(payload.patient_id, payload.analyte, payload.value, payload.unit)

    result = supabase_admin.table("lab_results").insert({
        "patient_id": payload.patient_id,
        "ordering_doc": user["id"],
        "analyte": payload.analyte,
        "value": payload.value,
        "unit": payload.unit,
        "ref_low": payload.ref_low,
        "ref_high": payload.ref_high,
        "severity": severity,
        "llm_context": llm_context
    }).execute()

    return result.data[0]

@router.get("/queue")
async def labs_queue(user: dict = Depends(require_permission("labs", "view"))):
    result = (
        supabase_admin.table("lab_results")
        .select("*")
        .in_("severity", ["abnormal", "critical"])
        .is_("acknowledged_at", "null")
        .order("severity")
        .execute()
    )

    rows = result.data
    rows.sort(key=lambda r: r["severity"] != "critical")
    return rows

@router.post("/{lab_result_id}/acknowledge")
async def acknowledge_lab_result(lab_result_id: str, user: dict = Depends(require_permission("labs", "edit"))):
    from datetime import datetime, timezone

    result = (
        supabase_admin.table("lab_results")
        .update({"acknowledged_by": user["id"], "acknowledged_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", lab_result_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Lab result not found")
    return result.data[0]

