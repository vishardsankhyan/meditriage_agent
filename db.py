# db.py
import sqlite3
import json
import datetime

def init_db():
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            filename TEXT PRIMARY KEY,
            content TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sms_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            message TEXT,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    return {"found": False, "message": "No previous records found for this patient ID. First-time visitor."}

def map_icd10(symptoms_list):
    text = " ".join(symptoms_list).lower()
    if "cut" in text or "bleeding" in text:
        return "S91.309A (Puncture/cut wound with hemorrhage, initial encounter)"
    elif "headache" in text or "severe headache" in text:
        return "R51.9 (Headache, unspecified / Neurological Priority)"
    elif "shoulder" in text:
        return "M25.511 (Pain in right shoulder)"
    elif "chest" in text or "heart" in text or "crushing" in text:
        return "R07.9 (Chest pain, unspecified)"
    elif "breath" in text or "lung" in text:
        return "R06.02 (Shortness of breath)"
    elif "leg" in text or "knee" in text:
        return "M25.569 (Pain in unspecified knee/lower extremity)"
    return "R69 (Illness, unspecified)"

def safety_supervisor_audit(pain, urgent, symptoms_list):
    """Agentic Clinical Peer Review: Catches contradictions and red flags"""
    text_blob = " ".join([str(s).lower() for s in symptoms_list])
    
    red_flags = [
        "chest pain", "crushing", "bleeding", "heavy bleeding", "cut", "breathing", 
        "unconscious", "stroke", "numbness", "severe headache", "headache", 
        "unbearable", "can't bear", "thunderclap", "dizziness", "confusion"
    ]
    
    has_red_flag = any(flag in text_blob for flag in red_flags)
    
    if has_red_flag and pain <= 4:
        return "⚠️ CONTRADICTION DETECTED: Low pain score with critical red flags (e.g., heavy bleeding/severe pain). PEER REVIEW OVERRIDE: Mandatory Emergency Escalation."
    elif pain >= 9 or urgent or (has_red_flag and pain >= 7):
        return "VERIFIED: Critical Emergency Protocol Required"
    elif pain >= 5:
        return "VERIFIED: Moderate Risk / Urgent Care Routing"
    return "VERIFIED: Routine Outpatient Clearance"

def log_sms_dispatch(patient_id, message):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sms_logs (patient_id, message, status) VALUES (?, ?, ?)", 
                   (patient_id, message, "DELIVERED (Twilio Simulated)"))
    conn.commit()
    conn.close()

def update_patient_record(data, transcript_summary="Patient completed secure voice intake successfully."):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    
    if hasattr(data, "dict"):
        data = data.dict()
        
    p_id = data.get("patient_id")
    symptoms_list = data.get("primary_symptoms", [])
    pain = data.get("pain_level")
    urgent_flag = data.get("requires_urgent_care", False)
    
    safety_audit = safety_supervisor_audit(pain, urgent_flag, symptoms_list)
    
    # FORCE ESCALATION & URGENT STATUS IF SAFETY SUPERVISOR OVERRIDES
    if "OVERRIDE" in safety_audit or "Critical Emergency" in safety_audit or urgent_flag:
        escalated = 1
        urgent = 1
    else:
        escalated = 1 if pain >= 9 else 0
        urgent = 1 if urgent_flag else 0
        
    icd10 = map_icd10(symptoms_list)
    
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, icd10_code, safety_status, transcript)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (p_id, json.dumps(symptoms_list), pain, urgent, escalated, icd10, safety_audit, transcript_summary))
    
    conn.commit()
    conn.close()
    
    sms_msg = f"MediTriage Notice: Patient {p_id} intake logged. Risk Tier: {'CRITICAL (OVERRIDE)' if escalated else 'Routine'}. ICD-10: {icd10}."
    log_sms_dispatch(p_id, sms_msg)
    
    return {"status": "success", "message": "EHR record, safety audit, and SMS dispatch complete.", "safety_audit": safety_audit}

def escalate_to_human(arguments, transcript_summary="Emergency escalation triggered."):
    p_id = arguments.get("patient_id", "UNKNOWN")
    reason = arguments.get("reason_for_escalation", "Critical emergency escalation requested.")
    
    safety_audit = safety_supervisor_audit(10, True, [reason])
    icd10 = map_icd10([reason])
    
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, icd10_code, safety_status, transcript)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (p_id, json.dumps([reason]), 10, 1, 1, icd10, "FLAGGED: Immediate Emergency Override (Safety Supervisor)", transcript_summary))
    conn.commit()
    conn.close()
    
    log_sms_dispatch(p_id, f"🚨 EMERGENCY ALERT: Patient {p_id} routed to on-call physician. Reason: {reason}")
    
    return {"status": "success", "message": "Call successfully routed to on-call ER nurse and SMS dispatched.", "safety_audit": safety_audit}

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
            if clean_query in p_lower or all(term in p_lower for term in clean_query.split() if len(term) > 3):
                results.append(f"[{filename}]: {p.strip()}")
                
    if not results:
        return {"found": False, "guidance": "No specific uploaded protocol found. Follow standard triage guidelines."}
    return {"found": True, "guidance": "\n\n".join(results[:1])}

init_db()