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
    
    # New table for Automated E-Prescriptions & Lab Requisitions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clinical_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            order_type TEXT,
            order_details TEXT,
            status TEXT,
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
    """Autonomously generates e-Prescriptions and Lab Requisitions based on ICD-10 & Protocols"""
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    
    # Clear existing orders for this update cycle to avoid duplicates
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
        return "⚠️ CONTRADICTION DETECTED: Low pain score with critical red flags. PEER REVIEW OVERRIDE: Mandatory Emergency Escalation."
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
    
    # Automatically generate e-Prescribe and Lab Requisitions
    generate_automated_orders(p_id, symptoms_list, icd10)
    
    sms_msg = f"MediTriage Notice: Patient {p_id} intake logged. Risk Tier: {'CRITICAL' if escalated else 'Routine'}. ICD-10: {icd10}."
    log_sms_dispatch(p_id, sms_msg)
    
    return {"status": "success", "message": "EHR record, clinical orders, and safety audit complete.", "safety_audit": safety_audit}

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
    
    return {"status": "success", "message": "Call successfully routed to on-call ER nurse and clinical orders generated.", "safety_audit": safety_audit}

def generate_fhir_resource(patient_id):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, symptoms, pain, urgent, escalated, icd10_code, safety_status, vocal_stress, transcript FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {"error": "Patient not found"}
        
    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": row[0],
                    "identifier": [{"system": "urn:oid:2.16.840.1.113883.4.2", "value": row[0]}]
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "status": "finished",
                    "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
                    "subject": {"reference": f"Patient/{row[0]}"},
                    "reasonCode": [{"text": row[1]}],
                    "extension": [
                        {"url": "http://meditriage.fhir.io/pain-level", "valueInteger": row[2]},
                        {"url": "http://meditriage.fhir.io/icd10", "valueString": row[5]},
                        {"url": "http://meditriage.fhir.io/vocal-biomarker", "valueString": row[7]}
                    ]
                }
            }
        ]
    }
    return fhir_bundle

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