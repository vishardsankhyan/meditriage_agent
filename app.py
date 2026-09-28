# app.py
import streamlit as st
import sqlite3
import pandas as pd
import json
import time
from db import (
    init_db, generate_fhir_resource, get_live_transcripts, 
    bridge_physician_call, add_doctor_whisper, approve_clinical_order, 
    get_active_sessions, get_patient_dossier, resolve_patient_escalation
)

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
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    .stMetric label { color: #8b949e !important; font-weight: 600; }
    .stMetric [data-testid="stMetricValue"] { color: #f0f6fc !important; }
    .dossier-card {
        background-color: #161b22;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #30363d;
        margin-bottom: 15px;
    }
    @keyframes pulse {
        0% { opacity: 1.0; }
        50% { opacity: 0.4; }
        100% { opacity: 1.0; }
    }
    .emergency-banner {
        background-color: #8b0000;
        color: white;
        padding: 14px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        animation: pulse 1.5s infinite;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
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

df = load_data()
orders_df = load_clinical_orders()
active_calls = get_active_sessions()

with st.sidebar:
    st.image("https://img.icons8.com/color/96/hospital-3.png", width=50)
    st.title("MediTriage Ops")
    st.markdown("Enterprise AI Clinical Suite")
    st.divider()
    
    st.subheader("⚡ System Telemetry")
    st.markdown(f"🟢 **Active Online Calls:** {len(active_calls)}")
    st.markdown("🤖 **Safety Supervisor:** Online")
    st.markdown("👤 **Patient 360 Engine:** Active")
    st.divider()
    
    auto_refresh = st.checkbox("🔄 Live Auto-Refresh (2s)", value=True)

st.title("🏥 MediTriage Enterprise Clinical Command Center")
st.markdown("Unified Patient 360° dossiers, real-time active call monitoring, AI messaging, and prescription approvals.")

active_emergencies = len(df[df['escalated'] == 1]) if not df.empty and 'escalated' in df else 0
if active_emergencies > 0:
    st.markdown(f"""
        <div class="emergency-banner">
            <span>🚨 CRITICAL ALERT: {active_emergencies} Active Emergency Escalation(s) Require Immediate Doctor Action!</span>
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

# TAB NAVIGATION
tab_patient_360, tab_queue, tab_monitor, tab_orders, tab_analytics = st.tabs([
    "👤 Patient 360° Master Record", 
    "📋 Severity Triage Queue", 
    "🔴 Live Calls & AI Communicator", 
    "💊 Lab & E-Prescribe Approvals", 
    "📊 ICD-10 & Analytics"
])

with tab_patient_360:
    st.subheader("👤 Unified Patient 360° Master Dossier")
    st.markdown("Instant correlation of clinical telemetry, prescriptions, communication logs, and voice transcripts.")
    
    if df.empty:
        st.info("No patient records available yet.")
    else:
        patient_ids = df['id'].tolist()
        selected_patient_id = st.selectbox("🔍 Select Patient ID to Inspect File", patient_ids)
        
        if selected_patient_id:
            dossier = get_patient_dossier(selected_patient_id)
            if dossier:
                st.divider()
                
                # --- EXECUTIVE HEADER KPI BAR ---
                h1, h2, h3, h4 = st.columns(4)
                with h1:
                    st.metric("Patient ID", dossier['patient_id'])
                with h2:
                    st.metric("Pain Severity", f"{dossier['pain']} / 10")
                with h3:
                    risk_label = "🔴 CRITICAL" if dossier['escalated'] else "🟢 ROUTINE"
                    st.metric("Clinical Risk Tier", risk_label)
                with h4:
                    st.metric("ICD-10 Code", dossier['icd10_code'].split(" ")[0])
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # --- TWO-COLUMN MASTER SPLIT LAYOUT ---
                col_left, col_right = st.columns([1.1, 0.9])
                
                with col_left:
                    st.markdown("### 🩺 Clinical Core & Prescriptions")
                    
                    try:
                        symptoms_display = ", ".join(json.loads(dossier['symptoms']))
                    except:
                        symptoms_display = dossier['symptoms']
                    
                    # Clinical Summary Card
                    st.markdown(f"""
                    <div class="dossier-card">
                        <h4 style="margin-top:0; color:#58a6ff;">Clinical Summary & Safety Audit</h4>
                        <p><b>Primary Symptoms:</b> {symptoms_display}</p>
                        <p><b>ICD-10 Diagnosis:</b> <code>{dossier['icd10_code']}</code></p>
                        <p><b>Vocal Biomarker:</b> {dossier['vocal_stress']}</p>
                        <p><b>Safety Supervisor Audit:</b> <code>{dossier['safety_status']}</code></p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Actionable Orders Card
                    st.markdown(f"""
                    <div class="dossier-card">
                        <h4 style="margin-top:0; color:#58a6ff;">Active Prescriptions & Lab Requisitions</h4>
                    """, unsafe_allow_html=True)
                    
                    orders = dossier['orders']
                    if not orders:
                        st.info("No clinical orders for this patient.")
                    else:
                        for o in orders:
                            o_id, o_type, details, status, timestamp = o
                            st.markdown(f"**{o_type}**: {details}")
                            st.markdown(f"*Status:* `{status}`")
                            if "Pending" in status:
                                if st.button("✅ Approve & Dispatch", key=f"d_app_{o_id}"):
                                    approve_clinical_order(o_id)
                                    st.success("Approved!")
                                    st.rerun()
                            else:
                                st.markdown("✔️ **Dispatched to EHR**")
                            st.divider()
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                with col_right:
                    st.markdown("### 📜 Interactive History & Timeline")
                    
                    # Compact & Expandable History Sections
                    with st.expander(f"🎙️ Verbatim Voice Intake Transcript", expanded=True):
                        st.code(dossier['transcript'], language="text")
                        
                    with st.expander(f"📱 SMS Dispatches ({len(dossier['sms'])} messages)", expanded=False):
                        sms_logs = dossier['sms']
                        if not sms_logs:
                            st.caption("No SMS dispatches recorded.")
                        else:
                            for msg, stat, ts in sms_logs:
                                st.markdown(f"**[{ts}]** `{stat}`\n> {msg}")
                                st.divider()
                                
                    with st.expander(f"👨‍⚕️ Physician Actions & Bridges ({len(dossier['actions'])} entries)", expanded=False):
                        actions = dossier['actions']
                        if not actions:
                            st.caption("No physician interventions recorded.")
                        else:
                            for act_type, note, stat, ts in actions:
                                st.markdown(f"**[{ts}]** `{act_type}`: {note} (`{stat}`)")
                                st.divider()
                        
                # --- FOOTER EXPORT BAR ---
                st.markdown("<br>", unsafe_allow_html=True)
                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    report_text = f"--- MEDITRIAGE CLINICAL DOSSIER ---\nPatient ID: {dossier['patient_id']}\nSymptoms: {symptoms_display}\nPain: {dossier['pain']}/10\nICD-10: {dossier['icd10_code']}\nSafety Audit: {dossier['safety_status']}\n----------------------------------"
                    st.download_button("📥 Download Official Clinical Report (TXT)", data=report_text, file_name=f"clinical_dossier_{selected_patient_id}.txt", mime="text/plain")
                with f_col2:
                    fhir_json = json.dumps(generate_fhir_resource(selected_patient_id), indent=2)
                    st.download_button("🌐 Export SMART on FHIR Bundle (JSON)", data=fhir_json, file_name=f"fhir_bundle_{selected_patient_id}.json", mime="application/json")

with tab_queue:
    st.subheader("📋 Severity-Segregated Patient Triage Queue & Action Center")
    if df.empty:
        st.info("No patient records found.")
    else:
        critical_df = df[(df['escalated'] == 1) | (df['pain'] >= 8) | (df['urgent'] == 1)]
        moderate_df = df[(df['escalated'] == 0) & (df['pain'] >= 5) & (df['pain'] < 8) & (df['urgent'] == 0)]
        routine_df = df[(df['escalated'] == 0) & (df['pain'] < 5) & (df['urgent'] == 0)]
        
        st.markdown("### 🔴 Critical / Emergency Tier (Action Required)")
        if critical_df.empty:
            st.success("No active critical escalations.")
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
                
                with st.expander(f"🔴 CRITICAL | Patient ID: {p_id} — {symptoms_str} (Pain: {pain}/10)", expanded=True):
                    col_q1, col_q2 = st.columns([3, 1])
                    with col_q1:
                        st.markdown(f"**Symptoms:** {symptoms_str}")
                        st.markdown(f"**ICD-10 Code:** `{icd10}`")
                        st.markdown(f"**Vocal Stress Index:** {vocal}")
                        st.markdown(f"**Safety Audit:** `{row.get('safety_status', 'N/A')}`")
                    with col_q2:
                        if st.button("✅ Mark Addressed & Resolve", key=f"resolve_{p_id}_{idx}"):
                            resolve_patient_escalation(p_id)
                            st.success(f"Resolved Patient {p_id}!")
                            st.rerun()
                        if st.button("📞 Bridge Call", key=f"bridge_q_{p_id}_{idx}"):
                            bridge_physician_call(p_id, "Emergency bridge requested from queue.")
                            st.success(f"Bridged to {p_id}!")
                            st.rerun()

        st.markdown("### 🟡 Moderate Risk Tier")
        if not moderate_df.empty:
            for idx, row in moderate_df.iterrows():
                st.text(f"Patient ID: {row['id']} — Pain: {row['pain']}/10 — ICD-10: {row.get('icd10_code', 'N/A')}")

        st.markdown("### 🟢 Routine Outpatient Tier")
        if not routine_df.empty:
            for idx, row in routine_df.iterrows():
                st.text(f"Patient ID: {row['id']} — Pain: {row['pain']}/10 — ICD-10: {row.get('icd10_code', 'N/A')}")

with tab_monitor:
    st.subheader("🔴 Live Active Calls & AI Communicator")
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
    orders_df = load_clinical_orders()
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

with tab_analytics:
    st.subheader("📊 Diagnostic ICD-10 Breakdown")
    df_analytics = load_data()
    if not df_analytics.empty and 'icd10_code' in df_analytics:
        code_counts = df_analytics['icd10_code'].value_counts().reset_index()
        code_counts.columns = ['ICD-10 Code', 'Count']
        st.dataframe(code_counts, use_container_width=True, hide_index=True)
    else:
        st.write("Awaiting live telemetry...")

if auto_refresh:
    time.sleep(2)
    st.rerun()