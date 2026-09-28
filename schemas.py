# schemas.py
from pydantic import BaseModel, Field
from typing import List

class PatientIntakeData(BaseModel):
    patient_id: str = Field(description="The 9-digit alphanumeric patient ID.")
    primary_symptoms: List[str] = Field(description="List of primary medical symptoms reported by the patient.")
    pain_level: int = Field(description="Patient's reported pain level on a scale from 1 to 10.")
    requires_urgent_care: bool = Field(description="True if symptoms indicate an immediate emergency or critical risk.")

class CheckClinicHours(BaseModel):
    day_of_week: str = Field(description="The day of the week to check clinic hours for (e.g., Monday, Saturday).")

class EscalateToHuman(BaseModel):
    patient_id: str = Field(description="The patient ID requiring live nurse transfer.")
    reason_for_escalation: str = Field(description="The clinical reason or critical symptoms driving the escalation.")

class LookupPatientHistory(BaseModel):
    patient_id: str = Field(description="The 9-digit patient ID to look up in historical EHR records.")

class ConsultKnowledgeBase(BaseModel):
    query: str = Field(description="Search query or symptom keyword to look up against uploaded clinic documents and protocols.")