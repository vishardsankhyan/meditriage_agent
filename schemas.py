# schemas.py
from pydantic import BaseModel, Field
from typing import List

class PatientIntakeData(BaseModel):
    patient_id: str = Field(
        ..., 
        description="The 9-digit alphanumeric patient ID provided by the caller.",
        min_length=9,
        max_length=9
    )
    primary_symptoms: List[str] = Field(
        ..., 
        description="A list of the main symptoms described by the patient."
    )
    pain_level: int = Field(
        ..., 
        description="The self-reported pain scale from 1 to 10."
    )
    requires_urgent_care: bool = Field(
        ...,
        description="Set to true if the patient mentions chest pain, severe bleeding, or difficulty breathing."
    )

class CheckClinicHours(BaseModel):
    day_of_week: str = Field(
        ..., 
        description="The day of the week the patient is asking about (e.g., 'Monday', 'Saturday')."
    )

class EscalateToHuman(BaseModel):
    patient_id: str = Field(
        ..., 
        description="The 9-digit alphanumeric patient ID."
    )
    reason_for_escalation: str = Field(
        ..., 
        description="A brief explanation of why the call is being transferred to a human nurse (e.g., 'Chest pain reported', 'Pain level 10')."
    )