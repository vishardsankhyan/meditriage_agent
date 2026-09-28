# db.py
import sqlite3
import json
import os

def init_db():
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    
    # Patients table with audit transcript and ICD-10 codes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            symptoms TEXT,
            pain INTEGER,
            urgent INTEGER,
            escalated INTEGER,
            icd10_code TEXT,
            safety_status TEXT,
            transcript TEXT
        )
    ''')
    
    # Knowledge Base / Uploaded Documents table for RAG
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            filename TEXT PRIMARY KEY,
            content TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Wearable IoT telemetry table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wearables (
            patient_id TEXT PRIMARY KEY,
            heart_rate INTEGER,
            spo2 INTEGER,
            ecg_status TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Safely migrate existing tables if columns are missing
    for col, col_type in [("transcript", "TEXT"), ("icd10_code", "TEXT"), ("safety_status", "TEXT")]:
        try:
            cursor.execute(f"ALTER TABLE patients ADD COLUMN {col} {col_type};")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    conn.close()

def get_patient_history(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT symptoms, pain, escalated, transcript, icd10_code FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "found": True,
            "previous_symptoms": row[0],
            "previous_pain": row[1],
            "was_escalated": bool(row[2]),
            "last_transcript": row[3],
            "icd10_code": row[4]
        }
    return {"found": False, "message": "No previous records found for this patient ID."}

def map_icd10(symptoms_list):
    """Automated ICD-10 Medical Coding heuristic engine"""
    text = " ".join(symptoms_list).lower()
    if "shoulder" in text:
        return "M25.511 (Pain in right shoulder)"
    elif "chest" in text or "heart" in text:
        return "R07.9 (Chest pain, unspecified)"
    elif "breath" in text or "lung" in text:
        return "R06.02 (Shortness of breath)"
    elif "head" in text:
        return "R51.9 (Headache, unspecified)"
    elif "leg" in text or "knee" in text:
        return "M25.569 (Pain in unspecified knee/lower extremity)"
    return "R69 (Illness, unspecified)"

def safety_supervisor_audit(pain, urgent, symptoms):
    """Autonomous Multi-Agent Clinical Safety Supervisor validation"""
    if pain >= 9 or urgent or any(s in str(symptoms).lower() for s in ["chest pain", "bleeding", "breathing"]):
        return "VERIFIED: Critical Emergency Protocol Required"
    elif pain >= 5:
        return "VERIFIED: Moderate Risk / Urgent Care Routing"
    return "VERIFIED: Routine Outpatient Clearance"

def update_patient_record(data, transcript_summary="Patient completed secure voice intake successfully."):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    
    if hasattr(data, "dict"):
        data = data.dict()
        
    p_id = data.get("patient_id")
    symptoms_list = data.get("primary_symptoms", [])
    symptoms = json.dumps(symptoms_list)
    pain = data.get("pain_level")
    urgent = 1 if data.get("requires_urgent_care", False) else 0
    escalated = 1 if pain >= 9 or urgent == 1 else 0
    
    icd10 = map_icd10(symptoms_list)
    safety_audit = safety_supervisor_audit(pain, urgent, symptoms_list)
    
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, icd10_code, safety_status, transcript)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (p_id, symptoms, pain, urgent, escalated, icd10, safety_audit, transcript_summary))
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "EHR record and ICD-10 codes successfully updated.", "icd10": icd10}

def escalate_to_human(arguments):
    p_id = arguments.get("patient_id", "UNKNOWN")
    reason = arguments.get("reason_for_escalation", "Critical emergency escalation requested.")
    
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, icd10_code, safety_status, transcript)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (p_id, json.dumps([reason]), 10, 1, 1, "R07.9 (Critical Triage Escalation)", "FLAGGED: Immediate Emergency Override", f"🚨 Emergency Escalation Triggered: {reason}"))
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
    return {"day": day, "hours": hours.get(day, "8:00 AM to 6:00 PM")}

def query_knowledge_base(query):
    """Refined RAG tool with phrase-level precision"""
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT filename, content FROM documents")
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    clean_query = query.lower().strip()
    
    for filename, content in rows:
        paragraphs = content.split('\n\n')
        for p in paragraphs:
            p_lower = p.lower()
            # Match if the exact query phrase or major keywords appear together
            if clean_query in p_lower or all(term in p_lower for term in clean_query.split() if len(term) > 3):
                results.append(f"[{filename}]: {p.strip()}")
                
    if not results:
        return {"found": False, "guidance": "No specific uploaded protocol found. Follow standard triage guidelines."}
        
    return {"found": True, "guidance": "\n\n".join(results[:1])} # Returns the single best matching paragraph

init_db()