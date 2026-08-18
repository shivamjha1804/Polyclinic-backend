from fastapi import Depends, Header, HTTPException
from app.db.client import supabase_admin


async def current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")

    token = authorization.removeprefix("Bearer ")

    try:
        user = supabase_admin.auth.get_user(token).user
    except Exception:
        raise HTTPException(401, "Invalid token")

    if user is None:
        raise HTTPException(401, "Invalid token")

    profile = (
        supabase_admin.table("profiles")
        .select("*").eq("id", user.id).single().execute()
    )
    return profile.data


def require_role(*roles: str):
    async def _check(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, "Insufficient role")
        return user
    return _check


def require_permission(resource: str, action: str):
    """Dynamic RBAC check: does this user's role have (resource, action)?

    'owner' is the superadmin and bypasses this check entirely -- it never
    needs explicit role_permissions rows.
    """
    async def _check(user: dict = Depends(current_user)) -> dict:
        if user["role"] == "owner":
            return user

        result = supabase_admin.rpc("role_has_permission", {
            "role_name": user["role"],
            "res": resource,
            "act": action,
        }).execute()

        if not result.data:
            raise HTTPException(403, "Insufficient permission")

        return user
    return _check
