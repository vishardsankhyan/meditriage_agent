# app.py
import streamlit as st
import sqlite3
import pandas as pd
import json
import time
from db import init_db, generate_fhir_resource

init_db()

st.set_page_config(
    page_title="MediTriage | Enterprise Clinical Suite",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #30363d;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stMetric label { color: #8b949e !important; font-weight: 600; }
    .stMetric [data-testid="stMetricValue"] { color: #f0f6fc !important; }
    @keyframes pulse {
        0% { opacity: 1.0; }
        50% { opacity: 0.4; }
        100% { opacity: 1.0; }
    }
    .emergency-banner {
        background-color: #8b0000;
        color: white;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        animation: pulse 1.5s infinite;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

def load_data():
    try:
        conn = sqlite3.connect('meditriage.db')
        df = pd.read_sql_query("SELECT * FROM patients", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "symptoms", "pain", "urgent", "escalated", "icd10_code", "safety_status", "vocal_stress", "transcript"])

def load_sms_logs():
    try:
        conn = sqlite3.connect('meditriage.db')
        df = pd.read_sql_query("SELECT * FROM sms_logs ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "patient_id", "message", "status", "timestamp"])

def save_uploaded_document(uploaded_file):
    content = uploaded_file.read().decode("utf-8", errors="ignore")
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO documents (filename, content) VALUES (?, ?)", (uploaded_file.name, content))
    conn.commit()
    conn.close()

def get_uploaded_documents():
    try:
        conn = sqlite3.connect('meditriage.db')
        cursor = conn.cursor()
        cursor.execute("SELECT filename, upload_date FROM documents")
        docs = cursor.fetchall()
        conn.close()
        return docs
    except Exception:
        return []

def update_case_status(patient_id, new_escalated_status):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET escalated = ? WHERE id = ?", (new_escalated_status, patient_id))
    conn.commit()
    conn.close()

df = load_data()
sms_df = load_sms_logs()

with st.sidebar:
    st.image("https://img.icons8.com/color/96/hospital-3.png", width=50)
    st.title("MediTriage Ops")
    st.markdown("Enterprise AI Clinical Suite")
    st.divider()
    
    st.subheader("📁 Agent Knowledge Base (RAG)")
    uploaded_file = st.file_uploader("Upload Clinical Protocol (.txt/.md)", type=["txt", "md"])
    if uploaded_file:
        save_uploaded_document(uploaded_file)
        st.success(f"Loaded '{uploaded_file.name}' into RAG memory!")
        
    docs = get_uploaded_documents()
    if docs:
        st.markdown("**Active Protocols:**")
        for doc in docs:
            st.text(f"• {doc[0]}")
            
    st.divider()
    st.subheader("⚡ System Telemetry")
    st.markdown("🟢 **Voice Gateway:** Connected")
    st.markdown("🧠 **Longitudinal Memory:** Active")
    st.markdown("🤖 **Safety Supervisor:** Online")
    st.markdown("🎙️ **Vocal Biomarkers:** Active")
    st.markdown("🌐 **SMART on FHIR:** Ready")
    st.divider()
    
    auto_refresh = st.checkbox("🔄 Live Auto-Refresh (2s)", value=True)

st.title("🏥 MediTriage Enterprise Clinical Command Center")
st.markdown("Autonomous voice intake, vocal biomarker stress analysis, SMART on FHIR export, and clinical handover reports.")

active_emergencies = len(df[df['escalated'] == 1]) if not df.empty and 'escalated' in df else 0
if active_emergencies > 0:
    st.markdown(f"""
        <div class="emergency-banner">
            🚨 CRITICAL ALERT: {active_emergencies} Active Emergency Escalation(s) Require Immediate Nurse Review!
        </div>
    """, unsafe_allow_html=True)

st.divider()

col1, col2, col3, col4 = st.columns(4)
total_intakes = len(df)
escalations = active_emergencies
urgent_cases = len(df[df['urgent'] == 1]) if not df.empty and 'urgent' in df else 0
avg_pain = round(df['pain'].mean(), 1) if not df.empty and 'pain' in df else 0

with col1:
    st.metric(label="Total Intakes", value=total_intakes, delta="Live DB")
with col2:
    st.metric(label="Emergency Escalations", value=escalations, delta_color="inverse")
with col3:
    st.metric(label="Urgent Care Flags", value=urgent_cases)
with col4:
    st.metric(label="Avg Reported Pain", value=f"{avg_pain} / 10")

st.divider()

tab_queue, tab_audit, tab_sms, tab_analytics = st.tabs([
    "📋 Active Triage Queue", 
    "🎙️ Call Audit & Clinical Reports", 
    "📱 Twilio SMS Dispatch Log", 
    "📊 ICD-10 & Analytics"
])

with tab_queue:
    st.subheader("Active Patient Intake Queue, Vocal Biomarkers & Safety Audits")
    if df.empty:
        st.info("No patient records found. Run `python agent.py` to initiate a live voice triage call!")
    else:
        for index, row in df.iterrows():
            p_id = row['id']
            try:
                symptoms_list = json.loads(row['symptoms'])
                symptoms_str = ", ".join(symptoms_list)
            except Exception:
                symptoms_str = str(row['symptoms'])
                
            pain = row['pain']
            escalated = row['escalated']
            urgent = row['urgent']
            icd10 = row.get('icd10_code', 'N/A')
            safety = row.get('safety_status', 'Pending Audit')
            vocal = row.get('vocal_stress', 'Normal')
            
            if pain >= 8 or urgent == 1 or escalated == 1 or "OVERRIDE" in str(safety) or "HIGH VOCAL" in str(vocal):
                risk_badge = "🔴 CRITICAL RISK"
                border_color = "#ff4b4b"
            elif pain >= 5:
                risk_badge = "🟡 MODERATE RISK"
                border_color = "#ffa726"
            else:
                risk_badge = "🟢 ROUTINE INTAKE"
                border_color = "#2e7d32"
                
            with st.container():
                st.markdown(f"""
                <div style="background-color: #161b22; padding: 15px; border-radius: 10px; border-left: 5px solid {border_color}; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #f0f6fc; font-size: 1.1em;">Patient ID: {p_id}</strong>
                        <span style="background: {border_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">{risk_badge}</span>
                    </div>
                    <p style="color: #8b949e; margin: 8px 0 4px 0;"><b>Symptoms:</b> {symptoms_str} &nbsp;|&nbsp; <b>ICD-10:</b> <code style="color: #58a6ff;">{icd10}</code></p>
                    <p style="color: #8b949e; margin: 0;"><b>Pain:</b> {pain}/10 &nbsp;|&nbsp; <b>Vocal Stress:</b> <span style="color: #ffa726;">{vocal}</span></p>
                </div>
                """, unsafe_allow_html=True)

with tab_audit:
    st.subheader("🎙️ Clinical Handoff Reports, FHIR Export & Verbatim Audits")
    if df.empty:
        st.info("No audit records available.")
    else:
        for index, row in df.iterrows():
            p_id = row['id']
            transcript = row.get('transcript', 'No transcript recorded.')
            icd10 = row.get('icd10_code', 'N/A')
            vocal = row.get('vocal_stress', 'Normal')
            pain = row['pain']
            try:
                symptoms_str = ", ".join(json.loads(row['symptoms']))
            except:
                symptoms_str = row['symptoms']
                
            with st.expander(f"📁 Session Handoff & Audit ID: {p_id}"):
                col_rep1, col_rep2 = st.columns(2)
                
                with col_rep1:
                    st.markdown("**📄 Official Clinical Handover Sheet:**")
                    report_text = f"""--- MEDITRIAGE CLINICAL HANDOFF REPORT ---
Patient ID: {p_id}
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}
Primary Symptoms: {symptoms_str}
Pain Level: {pain}/10
ICD-10 Code: {icd10}
Vocal Biomarker Stress: {vocal}

SOAP NOTE:
- S (Subjective): Patient reports {symptoms_str}. Pain rated at {pain}/10.
- O (Objective): Voice intake processed via AssemblyAI Real-Time Voice Gateway. Vocal stress index evaluated as {vocal}.
- A (Assessment): Patient prioritized under clinical guidelines. ICD-10 assigned: {icd10}.
- P (Plan): Routine or emergency routing synchronized with EHR database.
--------------------------------------------"""
                    st.download_button(
                        label="📥 Download Clinical Report (TXT)",
                        data=report_text,
                        file_name=f"meditriage_report_{p_id}.txt",
                        mime="text/plain",
                        key=f"rep_{p_id}"
                    )
                    
                with col_rep2:
                    st.markdown("**🌐 SMART on FHIR Interoperability JSON:**")
                    fhir_json = json.dumps(generate_fhir_resource(p_id), indent=2)
                    st.download_button(
                        label="📥 Export FHIR Bundle (JSON)",
                        data=fhir_json,
                        file_name=f"fhir_patient_{p_id}.json",
                        mime="application/json",
                        key=f"fhir_{p_id}"
                    )
                    
                st.divider()
                st.markdown("**🔍 Verbatim Audio Audit Transcript:**")
                st.code(transcript, language="text")

with tab_sms:
    st.subheader("📱 Twilio Out-of-Band SMS Dispatch Log")
    if sms_df.empty:
        st.info("No SMS dispatches logged yet.")
    else:
        st.dataframe(sms_df, use_container_width=True, hide_index=True)

with tab_analytics:
    st.subheader("📊 Diagnostic ICD-10 Breakdown")
    if not df.empty and 'icd10_code' in df:
        code_counts = df['icd10_code'].value_counts().reset_index()
        code_counts.columns = ['ICD-10 Code', 'Count']
        st.dataframe(code_counts, use_container_width=True, hide_index=True)
    else:
        st.write("Awaiting live intake telemetry...")

if auto_refresh:
    time.sleep(2)
    st.rerun()