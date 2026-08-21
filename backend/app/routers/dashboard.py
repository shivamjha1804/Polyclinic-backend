from datetime import datetime, timezone
import psycopg
from fastapi import APIRouter, Depends
from app.deps import current_user
from app.db.client import supabase_admin
from app.config import settings
from app.agents.followup import get_overdue_followups, get_overdue_referrals

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# ---- Widgets: one function per data section, each tied to a permission ----

def _widget_consultations(user: dict) -> dict:
    consultations = (
        supabase_admin.table("consultations")
        .select("patient_id, status")
        .eq("doctor_id", user["id"])
        .execute()
    ).data
    return {
        "total_patients_seen": len({c["patient_id"] for c in consultations}),
        "total_consultations": len(consultations),
        "signed_consultations": len([c for c in consultations if c["status"] == "signed"]),
    }


def _widget_labs(user: dict) -> dict:
    queue = (
        supabase_admin.table("lab_results")
        .select("id, analyte, severity")
        .in_("severity", ["abnormal", "critical"])
        .is_("acknowledged_at", "null")
        .execute()
    ).data
    return {"lab_queue": queue, "lab_queue_count": len(queue)}


def _widget_followups(user: dict) -> dict:
    return {
        "overdue_followups": get_overdue_followups(),
        "overdue_referrals": get_overdue_referrals(),
    }


def _widget_analytics(user: dict) -> dict:
    patient_count = len(supabase_admin.table("profiles").select("id").eq("role", "patient").execute().data)
    doctor_count = len(supabase_admin.table("profiles").select("id").eq("role", "doctor").execute().data)
    return {"total_patients": patient_count, "total_doctors": doctor_count}


def _widget_appointments_today(user: dict) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
    appointments = (
        supabase_admin.table("appointments")
        .select("id, patient_id, doctor_id, starts_at, status")
        .gte("starts_at", today_start)
        .lte("starts_at", today_end)
        .order("starts_at")
        .execute()
    ).data
    return {"todays_appointments": appointments, "todays_appointment_count": len(appointments)}


# Maps a (resource, action) permission to the widget that renders it. Whatever
# permissions a role holds, its dashboard is assembled from the matching widgets --
# grant a new permission to a role at runtime and that role's dashboard gains the
# section immediately, no code change or deploy needed.
WIDGETS = {
    ("consultations", "view"): _widget_consultations,
    ("consultations", "edit"): _widget_consultations,
    ("labs", "view"): _widget_labs,
    ("followups", "view"): _widget_followups,
    ("analytics", "view"): _widget_analytics,
}


def _role_permissions(role_name: str) -> list[tuple[str, str]]:
    conn = psycopg.connect(settings.SUPABASE_DB_URL)
    cur = conn.cursor()
    cur.execute("""
        select p.resource, p.action
        from role_permissions rp
        join roles r on r.id = rp.role_id
        join permissions p on p.id = rp.permission_id
        where r.name = %s
    """, (role_name,))
    rows = cur.fetchall()
    conn.close()
    return rows


def _patient_dashboard(user: dict) -> dict:
    # Patients aren't part of the staff permission system -- they always see their
    # own health data, not a permission-assembled view.
    records = (
        supabase_admin.table("medical_records")
        .select("id, title, doc_type, summary, recorded_at")
        .eq("patient_id", user["id"])
        .order("recorded_at", desc=True)
        .execute()
    ).data

    lab_history = (
        supabase_admin.table("lab_results")
        .select("analyte, value, unit, severity, created_at")
        .eq("patient_id", user["id"])
        .order("created_at")
        .execute()
    ).data

    now = datetime.now(timezone.utc).isoformat()
    upcoming_appointments = (
        supabase_admin.table("appointments")
        .select("id, doctor_id, starts_at, status")
        .eq("patient_id", user["id"])
        .gt("starts_at", now)
        .order("starts_at")
        .execute()
    ).data

    return {
        "role": "patient",
        "records": records,
        "lab_history": lab_history,
        "upcoming_appointments": upcoming_appointments,
    }


@router.get("")
async def dashboard(user: dict = Depends(current_user)):
    if user["role"] == "patient":
        return _patient_dashboard(user)

    # Owner bypasses the permission system entirely (superadmin) -- it has no
    # explicit role_permissions rows, so give it every widget directly.
    if user["role"] == "owner":
        sections: dict = {}
        for widget_fn in {fn for fn in WIDGETS.values()}:
            sections.update(widget_fn(user))
        sections.update(_widget_appointments_today(user))
        return {"role": "owner", **sections}

    permissions = _role_permissions(user["role"])

    sections: dict = {}
    seen_widgets = set()
    for resource, action in permissions:
        widget_fn = WIDGETS.get((resource, action))
        if widget_fn and widget_fn not in seen_widgets:
            sections.update(widget_fn(user))
            seen_widgets.add(widget_fn)

    if not sections:
        return {
            "role": user["role"],
            "message": "No dashboard widgets available yet -- this role has no permissions mapped to a widget.",
        }

    return {"role": user["role"], **sections}
