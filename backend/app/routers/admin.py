from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.deps import require_role
from app.db.client import supabase_admin

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- Staff account management ----

class StaffCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str
    specialty: str | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None
    slot_duration_minutes: int | None = None


@router.post("/staff")
async def create_staff(payload: StaffCreate, user: dict = Depends(require_role("owner"))):
    valid_roles = {r["name"] for r in supabase_admin.table("roles").select("name").execute().data}
    if payload.role not in valid_roles:
        raise HTTPException(400, f"Unknown role '{payload.role}'. Create it first via POST /admin/roles.")

    result = supabase_admin.auth.admin.create_user({
        "email": payload.email,
        "password": payload.password,
        "email_confirm": True,
    })
    staff_id = result.user.id

    profile = supabase_admin.table("profiles").insert({
        "id": staff_id,
        "role": payload.role,
        "full_name": payload.full_name,
        "specialty": payload.specialty,
        "working_hours_start": payload.working_hours_start,
        "working_hours_end": payload.working_hours_end,
        "slot_duration_minutes": payload.slot_duration_minutes,
    }).execute()

    return profile.data[0]


# ---- Role management ----

class RoleCreate(BaseModel):
    name: str


@router.post("/roles")
async def create_role(payload: RoleCreate, user: dict = Depends(require_role("owner"))):
    result = supabase_admin.table("roles").insert({"name": payload.name}).execute()
    return result.data[0]


@router.get("/roles")
async def list_roles(user: dict = Depends(require_role("owner"))):
    return supabase_admin.table("roles").select("*").execute().data


@router.get("/permissions")
async def list_permissions(user: dict = Depends(require_role("owner"))):
    return supabase_admin.table("permissions").select("*").execute().data


class PermissionAssignment(BaseModel):
    resource: str
    action: str


@router.post("/roles/{role_name}/permissions")
async def grant_permission(role_name: str, payload: PermissionAssignment, user: dict = Depends(require_role("owner"))):
    role = supabase_admin.table("roles").select("id").eq("name", role_name).single().execute().data
    if role is None:
        raise HTTPException(404, "Role not found")

    permission = (
        supabase_admin.table("permissions")
        .select("id").eq("resource", payload.resource).eq("action", payload.action).single().execute()
    ).data
    if permission is None:
        raise HTTPException(404, "Permission not found")

    supabase_admin.table("role_permissions").insert({
        "role_id": role["id"],
        "permission_id": permission["id"],
    }).execute()

    return {"status": "granted", "role": role_name, "resource": payload.resource, "action": payload.action}


@router.delete("/roles/{role_name}/permissions")
async def revoke_permission(role_name: str, payload: PermissionAssignment, user: dict = Depends(require_role("owner"))):
    role = supabase_admin.table("roles").select("id").eq("name", role_name).single().execute().data
    if role is None:
        raise HTTPException(404, "Role not found")

    permission = (
        supabase_admin.table("permissions")
        .select("id").eq("resource", payload.resource).eq("action", payload.action).single().execute()
    ).data
    if permission is None:
        raise HTTPException(404, "Permission not found")

    supabase_admin.table("role_permissions").delete().eq("role_id", role["id"]).eq("permission_id", permission["id"]).execute()

    return {"status": "revoked", "role": role_name, "resource": payload.resource, "action": payload.action}
