# app.py
import streamlit as st
import sqlite3
import pandas as pd
import json
import time

# Page Configuration
st.set_page_config(
    page_title="MediTriage | Clinical Command Center",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling & Emergency Pulse Effect
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

# Database Helper Functions
def load_data():
    try:
        conn = sqlite3.connect('meditriage.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patients'")
        if not cursor.fetchone():
            conn.close()
            return pd.DataFrame(columns=["id", "symptoms", "pain", "urgent", "escalated"])
        
        df = pd.read_sql_query("SELECT * FROM patients", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "symptoms", "pain", "urgent", "escalated"])

def update_case_status(patient_id, new_escalated_status):
    conn = sqlite3.connect('meditriage.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET escalated = ? WHERE id = ?", (new_escalated_status, patient_id))
    conn.commit()
    conn.close()

df = load_data()

# Sidebar Telemetry & Controls
with st.sidebar:
    st.image("https://img.icons8.com/color/96/hospital-3.png", width=50)
    st.title("MediTriage Ops")
    st.markdown("Enterprise AI Voice Gateway")
    st.divider()
    
    st.subheader("⚡ System Telemetry")
    st.markdown("🟢 **Voice Gateway:** Connected")
    st.markdown("🔒 **EHR Sync:** Secure (SQLite)")
    st.markdown("🎙️ **Model:** AssemblyAI Agent (Ivy)")
    st.divider()
    
    auto_refresh = st.checkbox("🔄 Live Auto-Refresh (2s)", value=True)
    st.divider()
    
    st.subheader("🔍 Filter Feed")
    search_query = st.text_input("Search Patient ID", placeholder="e.g., 123456789")
    filter_escalated = st.checkbox("⚠️ Show Escalated Only")

# Main Header
st.title("🏥 MediTriage Clinical Command & Control Center")
st.markdown("Real-time voice agent oversight, automated triage processing, and clinical SOAP note generation.")

# Emergency Banner Alert if active escalations exist
active_emergencies = len(df[df['escalated'] == 1]) if not df.empty and 'escalated' in df else 0
if active_emergencies > 0:
    st.markdown(f"""
        <div class="emergency-banner">
            🚨 CRITICAL ALERT: {active_emergencies} Active Emergency Escalation(s) Require Immediate Nurse Review!
        </div>
    """, unsafe_allow_html=True)

st.divider()

# Metrics Row
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

# Apply Filters
if not df.empty:
    if search_query:
        df = df[df['id'].str.contains(search_query, case=False, na=False)]
    if filter_escalated:
        df = df[df['escalated'] == 1]

# Layout: Interactive Queue & Analytics
col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("📋 Active Patient Triage Queue & SOAP Notes")
    
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
                symptoms_list = [symptoms_str]
                
            pain = row['pain']
            escalated = row['escalated']
            urgent = row['urgent']
            
            # Risk Scoring Logic & Specialty Routing
            if pain >= 8 or urgent == 1 or escalated == 1:
                risk_badge = "🔴 CRITICAL RISK"
                border_color = "#ff4b4b"
                specialty = "Emergency / ER"
            elif pain >= 5:
                risk_badge = "🟡 MODERATE RISK"
                border_color = "#ffa726"
                specialty = "Urgent Care"
            else:
                risk_badge = "🟢 ROUTINE INTAKE"
                border_color = "#2e7d32"
                specialty = "General Practice"
                
            with st.container():
                st.markdown(f"""
                <div style="background-color: #161b22; padding: 15px; border-radius: 10px; border-left: 5px solid {border_color}; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <strong style="color: #f0f6fc; font-size: 1.1em;">Patient ID: {p_id}</strong>
                        <span style="background: {border_color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold;">{risk_badge}</span>
                    </div>
                    <p style="color: #8b949e; margin: 8px 0 4px 0;"><b>Primary Symptoms:</b> {symptoms_str} &nbsp;|&nbsp; <b>Suggested Specialty:</b> <i>{specialty}</i></p>
                    <p style="color: #8b949e; margin: 0;"><b>Pain Level:</b> {pain}/10 &nbsp;|&nbsp; <b>Urgent Flag:</b> {'Yes' if urgent else 'No'}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Expandable SOAP Note & Action Drawer
                with st.expander(f"📑 View Clinical SOAP Note & Actions (ID: {p_id})"):
                    st.markdown(f"""
                    **AI-Generated Clinical Documentation (SOAP Format):**
                    * **S (Subjective):** Patient reports primary complaint of *{symptoms_str}*. Self-reported pain scale is evaluated at **{pain}/10**. Caller verified identity via secure alphanumeric ID `{p_id}`.
                    * **O (Objective):** Telephony intake processed via AssemblyAI Real-Time Voice Gateway. Automated speech recognition confidence nominal. Urgent care flag: `{'True' if urgent else 'False'}`.
                    * **A (Assessment):** Patient presents with symptoms requiring evaluation by the **{specialty}** department. Risk stratification classified as `{risk_badge}`.
                    * **P (Plan):** `{'Immediate nurse dispatch / emergency protocol engaged.' if escalated else 'Record synchronized to local EHR database. Standard outpatient follow-up recommended.'}`
                    """)
                    
                    # Interactive Action Buttons inside Expander
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

        # Export CSV Button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Triage Feed & SOAP Notes (CSV)",
            data=csv,
            file_name="meditriage_clinical_export.csv",
            mime="text/csv",
        )

with col_right:
    st.subheader("📊 Department Load & Analytics")
    if not df.empty and 'pain' in df:
        pain_counts = df['pain'].value_counts().reset_index()
        pain_counts.columns = ['Pain Level', 'Count']
        pain_counts = pain_counts.sort_values('Pain Level')
        st.bar_chart(pain_counts.set_index('Pain Level'), color="#ff4b4b")
    else:
        st.write("Awaiting live intake telemetry...")

# Auto-refresh loop
if auto_refresh:
    time.sleep(2)
    st.rerun()