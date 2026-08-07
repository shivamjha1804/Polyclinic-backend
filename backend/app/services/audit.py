from app.db.client import supabase_admin

def log_action(actor_id: str, actor_role: str, action: str, resource_type: str = None, resource_id: str = None, metadata: dict = None):
    supabase_admin.table("audit_log").insert({
        "actor_id": actor_id,
        "actor_role": actor_role,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "metadata": metadata or {}
    }).execute()