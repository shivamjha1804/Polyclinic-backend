from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import consultations, records, analytics, internal, labs, admin, dashboard, appointments, doctors, intake, payments

app = FastAPI()

# Dev-only permissive CORS so local test pages (file://, localhost) can call
# the API directly. This must be restricted to the real frontend origin
# before deploy -- tracked as a known gap (roadmap PH12).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(intake.router)
app.include_router(payments.router)
