from datetime import datetime, timedelta, timezone
from app.db.client import supabase_admin

def get_available_slots(doctor_id: str, date: str) -> list[dict]:
    doctor= (
        supabase_admin.table("profiles")
        .select("working_hours_start, working_hours_end, slot_duration_minutes")
        .eq("id", doctor_id)
        .single()
        .execute()
    ).data

    if doctor is None or doctor["working_hours_start"] is None or doctor["working_hours_end"] is None:
        return []

    day = datetime.strptime(date, "%Y-%m-%d").date()
    start_h, start_m = map(int, doctor["working_hours_start"].split(":")[:2])
    end_h, end_m = map(int, doctor["working_hours_end"].split(":")[:2])
    slot_minutes = doctor["slot_duration_minutes"] or 30

    day_start = datetime(day.year, day.month, day.day, start_h, start_m, tzinfo=timezone.utc)
    day_end= datetime(day.year, day.month, day.day, end_h, end_m, tzinfo=timezone.utc)

    slots = []
    current = day_start

    while current + timedelta(minutes=slot_minutes) <= day_end:
        slots.append(current)
        current += timedelta(minutes=slot_minutes)

    existing = (
        supabase_admin.table("appointments")
        .select("starts_at")
        .eq("doctor_id", doctor_id)
        .gte("starts_at", day_start.isoformat())
        .lt("starts_at", (day_start + timedelta(days=1)).isoformat())
        .in_("status", ["booked", "pending_payment"])
        .execute()
    ).data

    taken = {datetime.fromisoformat(row["starts_at"].replace("Z", "+00:00")) for row in existing}
    available = [s for s in slots if s not in taken]

    return [
        {"starts_at": s.isoformat(), "ends_at": (s + timedelta(minutes=slot_minutes)).isoformat()}
        for s in available
    ]
