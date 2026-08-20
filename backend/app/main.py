from fastapi import FastAPI
from app.routers import consultations, records, analytics, internal, labs, admin, dashboard, appointments, doctors

app = FastAPI()

@app.get("/health")
async def health():
    return {"status" : "ok"}

app.include_router(consultations.router)
app.include_router(records.router)
app.include_router(analytics.router)
app.include_router(internal.router)
app.include_router(labs.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(appointments.router)
app.include_router(doctors.router)
