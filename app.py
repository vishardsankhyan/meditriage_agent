# app.py
import streamlit as st
import sqlite3
import pandas as pd
import json
import time
from db import init_db

# Ensure all database tables (patients, documents, wearables) are initialized on startup
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
        return pd.DataFrame(columns=["id", "symptoms", "pain", "urgent", "escalated", "icd10_code", "safety_status", "transcript"])

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

with st.sidebar:
    st.image("https://img.icons8.com/color/96/hospital-3.png", width=50)
    st.title("MediTriage Ops")
    st.markdown("Enterprise AI Clinical Suite")
    st.divider()
    
    st.subheader("📁 Agent Knowledge Base (RAG)")
    uploaded_file = st.file_uploader("Upload Clinical Protocol (.txt/.md)", type=["txt", "md"])
    if uploaded_file:
        save_uploaded_document(uploaded_file)
        st.success(f"Loaded '{uploaded_file.name}' into Agent RAG memory!")
        
    docs = get_uploaded_documents()
    if docs:
        st.markdown("**Active Uploaded Protocols:**")
        for doc in docs:
            st.text(f"• {doc[0]}")
            
    st.divider()
    st.subheader("⚡ System Telemetry")
    st.markdown("🟢 **Voice Gateway:** Connected")
    st.markdown("🧠 **RAG Engine:** Active")
    st.markdown("🤖 **Safety Supervisor:** Online")
    st.divider()
    
    auto_refresh = st.checkbox("🔄 Live Auto-Refresh (2s)", value=True)

st.title("🏥 MediTriage Enterprise Clinical Command Center")
st.markdown("Autonomous voice intake, automated ICD-10 coding, multi-agent safety supervision, and RAG document intelligence.")

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

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📋 Active Patient Triage Queue, ICD-10 Codes & Safety Audits")
    
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
            transcript = row.get('transcript', 'No transcript recorded.')
            
            if pain >= 8 or urgent == 1 or escalated == 1:
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
                    <p style="color: #8b949e; margin: 8px 0 4px 0;"><b>Symptoms:</b> {symptoms_str} &nbsp;|&nbsp; <b>ICD-10 Code:</b> <code style="color: #58a6ff;">{icd10}</code></p>
                    <p style="color: #8b949e; margin: 0;"><b>Pain:</b> {pain}/10 &nbsp;|&nbsp; <b>Safety Supervisor:</b> <span style="color: #3fb950;">{safety}</span></p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander(f"📑 View Clinical SOAP Note, ICD-10 & Verbatim Audit (ID: {p_id})"):
                    st.markdown(f"""
                    **AI-Generated Clinical Documentation (SOAP Format with ICD-10):**
                    * **S (Subjective):** Patient reports primary complaint of *{symptoms_str}*. Self-reported pain scale is evaluated at **{pain}/10**. Caller verified via ID `{p_id}`.
                    * **O (Objective):** AssemblyAI Real-Time Voice Gateway intake. ICD-10 Billing Code assigned: `{icd10}`. Urgent care flag: `{'True' if urgent else 'False'}`.
                    * **A (Assessment):** Multi-Agent Safety Supervisor Status: `{safety}`. Risk stratification: `{risk_badge}`.
                    * **P (Plan):** `{'Immediate nurse dispatch / emergency protocol engaged.' if escalated else 'Record synchronized to local EHR database. Outpatient follow-up.'}`
                    """)
                    
                    st.divider()
                    st.markdown("**🔍 Verbatim Audio Audit Transcript:**")
                    st.code(transcript, language="text")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if escalated == 0:
                            if st.button("⚠️ Escalate Case", key=f"esc_{p_id}_{index}"):
                                update_case_status(p_id, 1)
                                st.rerun()
                        else:
                            if st.button("✅ Resolve / Clear", key=f"res_{p_id}_{index}"):
                                update_case_status(p_id, 0)
                                st.rerun()
                st.write("")

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Enterprise EHR Feed (CSV)",
            data=csv,
            file_name="meditriage_enterprise_export.csv",
            mime="text/csv",
        )

with col_right:
    st.subheader("📊 Live ICD-10 Diagnostic Breakdown")
    if not df.empty and 'icd10_code' in df:
        code_counts = df['icd10_code'].value_counts().reset_index()
        code_counts.columns = ['ICD-10 Code', 'Count']
        st.dataframe(code_counts, use_container_width=True, hide_index=True)
    else:
        st.write("Awaiting live intake telemetry...")

if auto_refresh:
    time.sleep(2)
    st.rerun()