from app.db.client import supabase_admin

AUDIO_BUCKET = "audio"

def create_audio_upload_url(consultation_id: str) -> dict:
    path = f"{consultation_id}/audio.webm"
    result = supabase_admin.storage.from_(AUDIO_BUCKET).create_signed_upload_url(path)
    return {"path" : path, "signed_url" : result["signed_url"], "token" : result["token"]}