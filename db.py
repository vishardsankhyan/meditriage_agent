# db.py
import sqlite3
import json

def init_db():
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            symptoms TEXT,
            pain INTEGER,
            urgent INTEGER,
            escalated INTEGER
        )
    ''')
    try:
        cursor.execute("ALTER TABLE patients ADD COLUMN transcript TEXT;")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def get_patient_history(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT symptoms, pain, escalated, transcript FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "found": True,
            "previous_symptoms": row[0],
            "previous_pain": row[1],
            "was_escalated": bool(row[2]),
            "last_transcript": row[3]
        }
    return {"found": False, "message": "No previous records found for this patient ID. First-time visitor."}

def update_patient_record(data, transcript_summary="Patient completed secure voice intake successfully."):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    
    if hasattr(data, "dict"):
        data = data.dict()
        
    p_id = data.get("patient_id")
    symptoms = json.dumps(data.get("primary_symptoms", []))
    pain = data.get("pain_level")
    urgent = 1 if data.get("requires_urgent_care", False) else 0
    escalated = 1 if pain >= 9 or urgent == 1 else 0
    
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, transcript)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (p_id, symptoms, pain, urgent, escalated, transcript_summary))
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "EHR record successfully updated."}

def escalate_to_human(arguments):
    p_id = arguments.get("patient_id", "UNKNOWN")
    reason = arguments.get("reason_for_escalation", "Critical emergency escalation requested.")
    
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, transcript)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (p_id, json.dumps([reason]), 10, 1, 1, f"🚨 Emergency Escalation Triggered: {reason}"))
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Call successfully routed to on-call ER nurse."}

def get_clinic_hours(day_of_week):
    hours = {
        "Monday": "8:00 AM to 6:00 PM",
        "Tuesday": "8:00 AM to 6:00 PM",
        "Wednesday": "8:00 AM to 6:00 PM",
        "Thursday": "8:00 AM to 6:00 PM",
        "Friday": "8:00 AM to 6:00 PM",
        "Saturday": "10:00 AM to 4:00 PM",
        "Sunday": "Closed"
    }
    day = day_of_week.capitalize()
    result = hours.get(day, "8:00 AM to 6:00 PM")
    return {"day": day, "hours": result}

init_db()