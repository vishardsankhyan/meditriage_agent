# 🏥 MediTriage | Enterprise Clinical Co-Pilot & Voice Triage Suite

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-red.svg)](https://streamlit.io/)
[![AssemblyAI](https://img.shields.io/badge/AssemblyAI-Voice%20Agent%20API-green.svg)](https://www.assemblyai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**MediTriage** is a production-grade, enterprise-ready clinical command center that bridges real-time generative voice AI with strict medical governance. Designed to augment medical professionals, MediTriage automates patient intake, calculates vocal stress biomarkers, performs autonomous ICD-10 diagnostic mapping, and provides robust human-in-the-loop physician intervention workflows.

---
## ✨ Key Features

* **🎙️ Real-Time Voice Intake Gateway:** Powered by the AssemblyAI Voice Agent API over secure WebSockets with barge-in support and sub-second voice responsiveness.
* **🔒 Strict 9-Digit UID Validation:** Enforces strict alphanumeric 9-digit patient identification across both telephony intake and administrative registration.
* **🛡️ Autonomous Safety Supervisor:** Audits patient responses against critical red-flag symptoms (e.g., chest pain, heavy bleeding) and flags contradictions regardless of reported pain levels.
* **📋 Severity-Segregated Triage Queue:** Organizes patient intakes into **Critical (Emergency)**, **Moderate**, and **Routine** tiers with one-click emergency resolution workflows.
* **👨‍⚕️ Doctor Intercom & Live Call Bridge:** Allows on-call physicians to monitor live transcripts, queue voice prompts for the AI to speak out loud ("Doctor Whisper"), or take over active calls.
* **💊 Custom E-Prescription & Email Dispatch:** Doctors can write custom prescriptions and lab requisitions that are logged in the EHR and securely dispatched via simulated email to the patient.
* **🌐 SMART on FHIR Interoperability:** Exports standardized JSON health bundles for seamless EHR integration.

---

## 🏛️ System Architecture

MediTriage utilizes a **Normalized Two-Table Relational Schema** to separate static patient demographics from dynamic clinical session telemetry:

```text
┌──────────────────────────────────────────────┐
│           patients (Master Profile)          │
│  - id (PK / 9-digit UID)                     │
│  - name, age, sex, phone, email              │
└──────────────────────┬───────────────────────┘
                       │ 1:N
                       ▼
┌──────────────────────────────────────────────┐
│       clinical_encounters (Telemetry)        │
│  - id (PK), uid (FK)                         │
│  - symptoms, pain, urgent, escalated         │
│  - icd10_code, vocal_stress, transcript      │
└──────────────────────────────────────────────┘

## Dataflow & Components 
** agent.py ** (Voice Telephony Worker): Manages real-time audio streaming, tool calls, and WebSocket events with AssemblyAI.

** app.py ** (Clinical Command Center): Streamlit dashboard providing multi-tab medical management, live auto-refreshing telemetry, and prescription approvals.

** db.py ** (EHR Data Engine): SQLite database layer handling self-healing schema migrations, secure profile storage, and audit logs.

---

## 🚀 Getting Started & Installation

### Prerequisites
* Python 3.10 or higher
* An **AssemblyAI API Key** ([Sign up here](https://www.assemblyai.com/))
* Working microphone and speaker (for voice agent simulations)

### 1. Clone the Repository
```bash
git clone [https://github.com/vishardsankhyan/meditriage_agent.git](hhttps://github.com/vishardsankhyan/meditriage_agent.git)
cd meditriage-agent
```

## 2. Set Up Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

## 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## 4. Configure Environment Variables
Create a .env file in the root directory and add your AssemblyAI API key:

Code snippet
```bash
ASSEMBLYAI_API_KEY=your_actual_api_key_here 
```
(Note: Ensure .env is included in your .gitignore file).

## 🎮 How to Run the Application
Because MediTriage operates as a real-time voice agent paired with a live clinical dashboard, run the application across two terminal windows:

### Terminal 1: Start the Real-Time Voice Agent
```bash
source .venv/bin/activate
python agent.py
```
* Behavior: Connects to AssemblyAI's WebSocket gateway, plays the greeting prompt, and listens for voice input.

## Terminal 2: Launch the Clinical Dashboard
```bash
source .venv/bin/activate
streamlit run app.py
```
* Behavior: Opens the Enterprise Command Center at http://localhost:8501.

## 🧪 Testing & Verification Guide
1. Patient Onboarding: Use the sidebar registration form in the dashboard to add a new patient with a strict 9-digit UID (e.g., 123456789).

2. Voice Intake Simulation: Run python agent.py and speak into your microphone. Provide your 9-digit UID and describe symptoms.

3. Severity Queue & Resolution: View the categorized queue in the dashboard. Click "✅ Mark Addressed & Resolve" on critical cases to test the emergency dismissal workflow.

4. Custom Prescriptions: Open the Patient 360° tab, select a patient, write a custom prescription, and verify the simulated email dispatch log.

## 🛡️ License
Distributed under the MIT License. See LICENSE for more information.

