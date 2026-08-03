from pydantic import BaseModel

class Medication(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str

class SoapNote(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str
    diagnosis: list[str]
    medications: list[Medication]
    follow_up: int | None

