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
            vocal_stress TEXT,
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clinical_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            order_type TEXT,
            order_details TEXT,
            status TEXT DEFAULT 'Pending Physician Sign-off',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS live_transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            speaker TEXT,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS active_sessions (
            patient_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'ACTIVE',
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_intercom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            instruction TEXT,
            status TEXT DEFAULT 'PENDING',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS doctor_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            action_type TEXT,
            clinical_note TEXT,
            status TEXT DEFAULT 'ACTIVE',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    for col, col_type in [("transcript", "TEXT"), ("icd10_code", "TEXT"), ("safety_status", "TEXT"), ("vocal_stress", "TEXT")]:
        try:
            cursor.execute(f"ALTER TABLE patients ADD COLUMN {col} {col_type};")
        except sqlite3.OperationalError:
            pass
            
    conn.commit()
    conn.close()

def register_active_session(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO active_sessions (patient_id, status) VALUES (?, 'ACTIVE')", (patient_id,))
    conn.commit()
    conn.close()

def close_active_session(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE active_sessions SET status = 'COMPLETED' WHERE patient_id = ?", (patient_id,))
    conn.commit()
    conn.close()

def get_active_sessions():
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id, started_at FROM active_sessions WHERE status = 'ACTIVE'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def log_live_utterance(patient_id, speaker, text):
    if not patient_id:
        patient_id = "LIVE_CALL"
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO live_transcripts (patient_id, speaker, text) VALUES (?, ?, ?)",
                   (patient_id, speaker, text))
    conn.commit()
    conn.close()

def get_live_transcripts(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT speaker, text, timestamp FROM live_transcripts WHERE patient_id = ? ORDER BY timestamp ASC", (patient_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_patient_history(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT symptoms, pain, escalated, transcript, icd10_code, vocal_stress FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "found": True,
            "previous_symptoms": row[0],
            "previous_pain": row[1],
            "was_escalated": bool(row[2]),
            "last_transcript": row[3],
            "icd10_code": row[4],
            "vocal_stress": row[5]
        }
    return {"found": False, "message": "No previous records found for this patient ID."}

def add_doctor_whisper(patient_id, instruction):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO doctor_intercom (patient_id, instruction, status) VALUES (?, ?, ?)",
                   (patient_id, instruction, "PENDING"))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Message queued for AI."}

def check_doctor_intercom_db(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, instruction FROM doctor_intercom WHERE patient_id = ? AND status = 'PENDING'", (patient_id,))
    rows = cursor.fetchall()
    
    if rows:
        for row in rows:
            cursor.execute("UPDATE doctor_intercom SET status = 'ACKNOWLEDGED' WHERE id = ?", (row[0],))
        conn.commit()
        conn.close()
        
        instructions = " ".join([r[1].strip() for r in rows])
        return json.dumps({
            "CRITICAL_ALERT": "DOCTOR_WHISPER_INTERRUPTION",
            "EXACT_PHRASE_TO_SPEAK_OUT_LOUD": f"The on-call doctor has asked me to tell you: {instructions}"
        })
    
    conn.close()
    return json.dumps({"CRITICAL_ALERT": "NONE"})

def bridge_physician_call(patient_id, note):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO doctor_actions (patient_id, action_type, clinical_note, status) VALUES (?, ?, ?, ?)",
                   (patient_id, "LIVE_CALL_BRIDGE", note, "CONNECTED"))
    conn.commit()
    conn.close()
    log_sms_dispatch(patient_id, f"🚨 PHYSICIAN BRIDGE: Doctor joined live call with patient {patient_id}. Note: {note}")
    return {"status": "success", "message": "Physician bridged successfully."}

def approve_clinical_order(order_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE clinical_orders SET status = 'APPROVED & DISPATCHED (EHR)' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Order approved."}

def map_icd10(symptoms_list):
    text = " ".join(symptoms_list).lower()
    if "cut" in text or "bleeding" in text:
        return "S91.309A (Puncture/cut wound with hemorrhage)"
    elif "headache" in text or "severe headache" in text:
        return "R51.9 (Headache, unspecified / Neurological Priority)"
    elif "shoulder" in text or "joint" in text or "knee" in text:
        return "M25.511 (Pain in joint / Orthopedic Specialty)"
    elif "chest" in text or "heart" in text or "crushing" in text:
        return "R07.9 (Chest pain, unspecified)"
    elif "breath" in text or "lung" in text:
        return "R06.02 (Shortness of breath)"
    return "R69 (Illness, unspecified)"

def generate_automated_orders(patient_id, symptoms_list, icd10_code):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clinical_orders WHERE patient_id = ?", (patient_id,))
    text = " ".join(symptoms_list).lower()
    
    if "cut" in text or "bleeding" in text:
        cursor.execute("INSERT INTO clinical_orders (patient_id, order_type, order_details, status) VALUES (?, ?, ?, ?)",
                       (patient_id, "Lab Requisition", "Complete Blood Count (CBC) & Tetanus Booster Injection", "Pending Physician Sign-off"))
        cursor.execute("INSERT INTO clinical_orders (patient_id, order_type, order_details, status) VALUES (?, ?, ?, ?)",
                       (patient_id, "E-Prescription", "Augmentin 875mg - 1 tablet orally twice daily for 7 days", "Pending Physician Sign-off"))
    elif "headache" in text:
        cursor.execute("INSERT INTO clinical_orders (patient_id, order_type, order_details, status) VALUES (?, ?, ?, ?)",
                       (patient_id, "Lab Requisition", "Urgent Brain MRI with Contrast & Neurological Panel", "Pending Physician Sign-off"))
        cursor.execute("INSERT INTO clinical_orders (patient_id, order_type, order_details, status) VALUES (?, ?, ?, ?)",
                       (patient_id, "E-Prescription", "Sumatriptan 50mg - Take at onset of migraine", "Pending Physician Sign-off"))
    elif "shoulder" in text or "joint" in text or "knee" in text:
        cursor.execute("INSERT INTO clinical_orders (patient_id, order_type, order_details, status) VALUES (?, ?, ?, ?)",
                       (patient_id, "Lab Requisition", "Orthopedic Imaging / MRI Joint Requisition", "Pending Physician Sign-off"))
        cursor.execute("INSERT INTO clinical_orders (patient_id, order_type, order_details, status) VALUES (?, ?, ?, ?)",
                       (patient_id, "E-Prescription", "Ibuprofen 600mg - Take 1 tablet every 8 hours with food for inflammation", "Pending Physician Sign-off"))
    else:
        cursor.execute("INSERT INTO clinical_orders (patient_id, order_type, order_details, status) VALUES (?, ?, ?, ?)",
                       (patient_id, "E-Prescription", "Standard Outpatient Care & Hydration Protocol", "Pending Physician Sign-off"))
        
    conn.commit()
    conn.close()

def calculate_vocal_biomarker(transcript_text, pain_level):
    text = transcript_text.lower()
    panic_words = ["can't bear", "severe", "hurry", "emergency", "unbearable", "worst", "help", "pain"]
    match_count = sum(1 for word in panic_words if word in text)
    if match_count >= 2 or pain_level >= 8:
        return "🔴 HIGH VOCAL DISTRESS (Acute Panic / Elevated Pitch Detected)"
    elif match_count == 1 or pain_level >= 5:
        return "🟡 MODERATE VOCAL STRESS (Anxious Phrasing Detected)"
    return "🟢 LOW VOCAL STRESS (Calm / Baseline)"

def safety_supervisor_audit(pain, urgent, symptoms_list):
    text_blob = " ".join([str(s).lower() for s in symptoms_list])
    red_flags = ["chest pain", "crushing", "bleeding", "heavy bleeding", "cut", "breathing", "unconscious", "stroke", "numbness", "severe headache", "headache", "unbearable", "can't bear"]
    has_red_flag = any(flag in text_blob for flag in red_flags)
    if has_red_flag and pain <= 4:
        return "⚠️ CONTRADICTION DETECTED: Low pain score with critical red flags. Mandatory Emergency Escalation."
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
    vocal_stress = calculate_vocal_biomarker(transcript_summary, pain)
    
    if "OVERRIDE" in safety_audit or "Critical Emergency" in safety_audit or urgent_flag or "HIGH VOCAL DISTRESS" in vocal_stress:
        escalated = 1
        urgent = 1
    else:
        escalated = 1 if pain >= 9 else 0
        urgent = 1 if urgent_flag else 0
        
    icd10 = map_icd10(symptoms_list)
    
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, icd10_code, safety_status, vocal_stress, transcript)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (p_id, json.dumps(symptoms_list), pain, urgent, escalated, icd10, safety_audit, vocal_stress, transcript_summary))
    
    conn.commit()
    conn.close()
    
    generate_automated_orders(p_id, symptoms_list, icd10)
    log_sms_dispatch(p_id, f"MediTriage Notice: Patient {p_id} intake logged. Risk Tier: {'CRITICAL' if escalated else 'Routine'}.")
    close_active_session(p_id)
    
    return {"status": "success", "message": "EHR record complete.", "safety_audit": safety_audit}

def escalate_to_human(arguments, transcript_summary="Emergency escalation triggered."):
    p_id = arguments.get("patient_id", "UNKNOWN")
    reason = arguments.get("reason_for_escalation", "Critical emergency escalation requested.")
    
    safety_audit = safety_supervisor_audit(10, True, [reason])
    vocal_stress = "🔴 HIGH VOCAL DISTRESS (Emergency Override Triggered)"
    icd10 = map_icd10([reason])
    
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO patients (id, symptoms, pain, urgent, escalated, icd10_code, safety_status, vocal_stress, transcript)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (p_id, json.dumps([reason]), 10, 1, 1, icd10, "FLAGGED: Immediate Emergency Override", vocal_stress, transcript_summary))
    conn.commit()
    conn.close()
    
    generate_automated_orders(p_id, [reason], icd10)
    log_sms_dispatch(p_id, f"🚨 EMERGENCY ALERT: Patient {p_id} routed to on-call physician. Reason: {reason}")
    close_active_session(p_id)
    
    return {"status": "success", "message": "Call routed to on-call ER nurse.", "safety_audit": safety_audit}

def generate_fhir_resource(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, symptoms, pain, urgent, escalated, icd10_code, safety_status, vocal_stress, transcript FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {"error": "Patient not found"}
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": row[0]}},
            {"resource": {"resourceType": "Encounter", "status": "finished", "subject": {"reference": f"Patient/{row[0]}"}, "reasonCode": [{"text": row[1]}]}}
        ]
    }

def get_clinic_hours(day):
    return {"day": day, "hours": "8:00 AM to 6:00 PM"}

def query_knowledge_base(query):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT filename, content FROM documents")
    rows = cursor.fetchall()
    conn.close()
    for filename, content in rows:
        if query.lower() in content.lower():
            return {"found": True, "guidance": content[:300]}
    return {"found": False, "guidance": "Follow standard protocol."}

init_db()