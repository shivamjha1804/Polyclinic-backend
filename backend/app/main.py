from fastapi import FastAPI, Depends
from app.deps import require_role
from app.routers import consultations, records

app = FastAPI()

@app.get("/health")
async def health():
    return {"status" : "ok"}

@app.get("/_test/doctor-only")
async def doctor_only(user: dict = Depends(require_role("doctor", "owner"))):
    return {"message" : f"Hello, {user['full_name']}, you have access to this endpoint because you are a doctor or owner."}

app.include_router(consultations.router)
app.include_router(records.router)
