import sqlite3
import json

def init_db():
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    # Added an 'escalated' column to track emergencies
    cursor.execute('''CREATE TABLE IF NOT EXISTS patients 
                 (id TEXT, symptoms TEXT, pain INTEGER, urgent BOOLEAN, escalated BOOLEAN)''')
    conn.commit()
    conn.close()

def update_patient_record(data_dict):
    init_db()
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO patients VALUES (?, ?, ?, ?, ?)",
              (data_dict['patient_id'], 
               json.dumps(data_dict['primary_symptoms']), 
               data_dict['pain_level'], 
               data_dict['requires_urgent_care'],
               False)) # Default to False
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Record saved to EHR."}

def escalate_to_human(data_dict):
    init_db()
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    # Log the patient but mark them as escalated
    cursor.execute("INSERT INTO patients VALUES (?, ?, ?, ?, ?)",
              (data_dict['patient_id'], 
               json.dumps([data_dict['reason_for_escalation']]), 
               10, # Assume max pain for emergency routing
               True, 
               True))
    conn.commit()
    conn.close()
    return {"status": "escalated", "message": "Call is being transferred to a live nurse."}

def get_clinic_hours(day):
    schedule = {
        "monday": "8:00 AM to 8:00 PM",
        "tuesday": "8:00 AM to 8:00 PM",
        "wednesday": "8:00 AM to 8:00 PM",
        "thursday": "8:00 AM to 8:00 PM",
        "friday": "8:00 AM to 8:00 PM",
        "saturday": "10:00 AM to 4:00 PM",
        "sunday": "Closed"
    }
    day_lower = day.lower()
    if day_lower in schedule:
        return {"hours": schedule[day_lower]}
    return {"hours": "I'm sorry, I couldn't understand the day."}