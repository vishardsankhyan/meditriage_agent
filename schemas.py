# schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class LookupPatientHistory(BaseModel):
    patient_id: str = Field(..., description="The 9-digit alphanumeric patient ID provided by the user.")

class ConsultKnowledgeBase(BaseModel):
    query: str = Field(..., description="The clinical search query or symptom keyword to look up in uploaded protocols.")

class CheckDoctorIntercom(BaseModel):
    patient_id: str = Field(..., description="The 9-digit patient ID currently active on the call.")

class PatientIntakeData(BaseModel):
    patient_id: str = Field(..., description="The 9-digit patient ID.")
    primary_symptoms: List[str] = Field(..., description="List of primary symptoms described by the patient.")
    pain_level: int = Field(..., description="Numeric pain score from 1 to 10.")
    requires_urgent_care: bool = Field(..., description="True if symptoms require urgent care or emergency escalation.")

class CheckClinicHours(BaseModel):
    day_of_week: str = Field(..., description="The day of the week to check clinic operating hours for.")

class EscalateToHuman(BaseModel):
    patient_id: str = Field(..., description="The 9-digit patient ID.")
    reason_for_escalation: str = Field(..., description="Detailed clinical reason for emergency escalation.")