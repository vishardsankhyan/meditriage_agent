# app.py
import streamlit as st
import sqlite3
import pandas as pd
import json
import time
from db import init_db, generate_fhir_resource, get_live_transcripts, bridge_physician_call, add_doctor_whisper, approve_clinical_order, get_active_sessions

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
        df = pd.read_sql_query("SELECT * FROM patients ORDER BY escalated DESC, pain DESC", conn)
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

def load_clinical_orders():
    try:
        conn = sqlite3.connect('meditriage.db')
        df = pd.read_sql_query("SELECT * FROM clinical_orders ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "patient_id", "order_type", "order_details", "status", "timestamp"])

def load_doctor_actions():
    try:
        conn = sqlite3.connect('meditriage.db')
        df = pd.read_sql_query("SELECT * FROM doctor_actions ORDER BY timestamp DESC", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "patient_id", "action_type", "clinical_note", "status", "timestamp"])

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

df = load_data()
sms_df = load_sms_logs()
orders_df = load_clinical_orders()
actions_df = load_doctor_actions()
active_calls = get_active_sessions()

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
    st.markdown(f"🟢 **Active Online Calls:** {len(active_calls)}")
    st.markdown("🤖 **Safety Supervisor:** Online")
    st.markdown("📞 **Live Call Bridge:** Active")
    st.markdown("🗣️ **AI Message Relay:** Ready")
    st.markdown("💊 **Lab Approvals:** Active")
    st.divider()
    
    auto_refresh = st.checkbox("🔄 Live Auto-Refresh (2s)", value=True)

st.title("🏥 MediTriage Enterprise Clinical Command Center")
st.markdown("Real-time active call monitoring, AI message communication, physician call bridging, and lab/prescription approval sign-off.")

active_emergencies = len(df[df['escalated'] == 1]) if not df.empty and 'escalated' in df else 0
if active_emergencies > 0:
    st.markdown(f"""
        <div class="emergency-banner">
            🚨 CRITICAL ALERT: {active_emergencies} Active Emergency Escalation(s) Require Immediate Doctor Action!
        </div>
    """, unsafe_allow_html=True)

st.divider()

col1, col2, col3, col4 = st.columns(4)
total_intakes = len(df)
escalations = active_emergencies
active_online = len(active_calls)
avg_pain = round(df['pain'].mean(), 1) if not df.empty and 'pain' in df else 0

with col1:
    st.metric(label="Active Online Calls", value=active_online, delta="Live WebSocket" if active_online > 0 else "Idle")
with col2:
    st.metric(label="Emergency Escalations", value=escalations, delta_color="inverse")
with col3:
    st.metric(label="Total Completed Intakes", value=total_intakes)
with col4:
    st.metric(label="Avg Reported Pain", value=f"{avg_pain} / 10")

st.divider()

tab_queue, tab_monitor, tab_orders, tab_audit, tab_sms, tab_analytics = st.tabs([
    "📋 Severity Triage Queue", 
    "🔴 Live Calls & AI Communicator", 
    "💊 Lab & E-Prescribe Approvals", 
    "🎙️ Call Audit & Reports", 
    "📱 Twilio SMS Log", 
    "📊 ICD-10 & Analytics"
])

with tab_queue:
    st.subheader("📋 Severity-Segregated Patient Triage Queue (Historical EHR)")
    st.markdown("Completed patient intaking sessions, categorized by clinical risk tier.")
    
    if df.empty:
        st.info("No patient records found. Run `python agent.py` to initiate a live voice triage call!")
    else:
        critical_df = df[(df['escalated'] == 1) | (df['pain'] >= 8) | (df['urgent'] == 1)]
        moderate_df = df[(df['escalated'] == 0) & (df['pain'] >= 5) & (df['pain'] < 8) & (df['urgent'] == 0)]
        routine_df = df[(df['escalated'] == 0) & (df['pain'] < 5) & (df['urgent'] == 0)]
        
        st.markdown("### 🔴 Critical / Emergency Triage Tier")
        if critical_df.empty:
            st.success("No critical records.")
        else:
            for idx, row in critical_df.iterrows():
                p_id = row['id']
                try:
                    symptoms_str = ", ".join(json.loads(row['symptoms']))
                except:
                    symptoms_str = row['symptoms']
                pain = row['pain']
                icd10 = row.get('icd10_code', 'N/A')
                vocal = row.get('vocal_stress', 'Normal')
                
                with st.expander(f"🔴 CRITICAL | Patient ID: {p_id} — Symptoms: {symptoms_str} (Pain: {pain}/10)"):
                    st.markdown(f"**Primary Symptoms:** {symptoms_str}")
                    st.markdown(f"**ICD-10 Code:** `{icd10}`")
                    st.markdown(f"**Pain Level:** {pain} / 10")
                    st.markdown(f"**Vocal Stress Index:** {vocal}")
                    st.markdown(f"**Safety Status:** `{row.get('safety_status', 'N/A')}`")

        st.markdown("### 🟡 Moderate Risk Tier")
        if moderate_df.empty:
            st.info("No moderate risk records.")
        else:
            for idx, row in moderate_df.iterrows():
                p_id = row['id']
                try:
                    symptoms_str = ", ".join(json.loads(row['symptoms']))
                except:
                    symptoms_str = row['symptoms']
                pain = row['pain']
                icd10 = row.get('icd10_code', 'N/A')
                
                with st.expander(f"🟡 MODERATE | Patient ID: {p_id} — Symptoms: {symptoms_str} (Pain: {pain}/10)"):
                    st.markdown(f"**Primary Symptoms:** {symptoms_str}")
                    st.markdown(f"**ICD-10 Code:** `{icd10}`")
                    st.markdown(f"**Pain Level:** {pain} / 10")

        st.markdown("### 🟢 Routine Outpatient Tier")
        if routine_df.empty:
            st.info("No routine records.")
        else:
            for idx, row in routine_df.iterrows():
                p_id = row['id']
                try:
                    symptoms_str = ", ".join(json.loads(row['symptoms']))
                except:
                    symptoms_str = row['symptoms']
                pain = row['pain']
                icd10 = row.get('icd10_code', 'N/A')
                
                with st.expander(f"🟢 ROUTINE | Patient ID: {p_id} — Symptoms: {symptoms_str} (Pain: {pain}/10)"):
                    st.markdown(f"**Primary Symptoms:** {symptoms_str}")
                    st.markdown(f"**ICD-10 Code:** `{icd10}`")
                    st.markdown(f"**Pain Level:** {pain} / 10")

with tab_monitor:
    st.subheader("🔴 Currently Active Online Calls (Live WebSocket Sessions)")
    st.markdown("Patients currently speaking with the AI voice agent appear here in real-time.")
    
    if not active_calls:
        st.info("ℹ️ No patients are currently online. Run `python agent.py` in your terminal to start a live voice call simulation!")
    else:
        active_ids = [call[0] for call in active_calls]
        selected_live_id = st.selectbox("Select Active Online Patient / Session ID", active_ids)
        
        col_mon1, col_mon2 = st.columns([1, 1])
        
        with col_mon1:
            st.markdown(f"### 🎙️ Live Transcript for: `{selected_live_id}`")
            live_rows = get_live_transcripts(selected_live_id)
            if live_rows:
                transcript_box = ""
                for speaker, text, timestamp in live_rows:
                    color = "#58a6ff" if speaker == "Agent" else "#3fb950"
                    transcript_box += f"<b style='color: {color};'>[{speaker}] ({timestamp}):</b> {text}<br>"
                st.markdown(f"""
                    <div style="background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; height: 300px; overflow-y: auto;">
                        {transcript_box}
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Waiting for speech utterance...")
                
        with col_mon2:
            st.markdown(f"### 🎛️ Doctor Actions for Active Call: `{selected_live_id}`")
            
            with st.form("ai_message_form"):
                st.markdown("**1. Communicate Message via AI Voice**")
                doctor_message = st.text_area("Message for AI to Speak Out Loud", placeholder="e.g., Ask if they are experiencing dizziness.")
                submit_ai_msg = st.form_submit_button("🗣️ Make AI Speak to Patient")
                
                if submit_ai_msg:
                    if doctor_message:
                        add_doctor_whisper(selected_live_id, doctor_message)
                        st.success(f"Message queued! The AI will voice this to Patient {selected_live_id} immediately.")
                    else:
                        st.warning("Please enter a message.")
                        
            st.divider()
            
            with st.form("bridge_form"):
                st.markdown("**2. Take Over / Bridge Live Call**")
                clinical_note = st.text_area("Physician Note", placeholder="e.g., Doctor taking over call directly.")
                submit_bridge = st.form_submit_button("🚨 Join / Bridge Live Call")
                
                if submit_bridge:
                    if clinical_note:
                        bridge_physician_call(selected_live_id, clinical_note)
                        st.success(f"Successfully bridged physician to active call {selected_live_id}!")
                    else:
                        st.warning("Please provide a physician note.")

with tab_orders:
    st.subheader("💊 Lab Requisition & E-Prescription Approvals")
    if orders_df.empty:
        st.info("No clinical orders generated yet.")
    else:
        for idx, row in orders_df.iterrows():
            o_id = row['id']
            p_id = row['patient_id']
            o_type = row['order_type']
            details = row['order_details']
            status = row['status']
            
            col_o1, col_o2, col_o3 = st.columns([3, 2, 1])
            with col_o1:
                st.markdown(f"**Patient:** `{p_id}` | **Type:** {o_type}")
                st.text(details)
            with col_o2:
                st.markdown(f"**Status:** `{status}`")
            with col_o3:
                if "Pending" in status:
                    if st.button("✅ Approve Lab / Rx", key=f"app_{o_id}"):
                        approve_clinical_order(o_id)
                        st.success("Approved & Dispatched!")
                        st.rerun()
                else:
                    st.markdown("✔️ **Approved**")
            st.divider()

with tab_audit:
    st.subheader("🎙️ Clinical Handoff Reports & FHIR Export")
    if df.empty:
        st.info("No audit records available.")
    else:
        for index, row in df.iterrows():
            p_id = row['id']
            transcript = row.get('transcript', 'No transcript recorded.')
            icd10 = row.get('icd10_code', 'N/A')
            with st.expander(f"📁 Session Audit ID: {p_id} (ICD-10: {icd10})"):
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
        st.write("Awaiting live telemetry...")

if auto_refresh:
    time.sleep(2)
    st.rerun()