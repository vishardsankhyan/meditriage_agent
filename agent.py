# agent.py
import asyncio
import websockets
import json
import os
import base64
import ssl
import queue
from dotenv import load_dotenv
from audio import Mic, Speaker
from db import update_patient_record, escalate_to_human, get_clinic_hours, get_patient_history, query_knowledge_base
from schemas import PatientIntakeData, CheckClinicHours, EscalateToHuman, LookupPatientHistory, ConsultKnowledgeBase

load_dotenv()

SYSTEM_PROMPT = """You are the receptionist and triage assistant for the MediTriage Medical Clinic. 
You must start the conversation by saying EXACTLY: "Hello, this is the MediTriage automated assistant. Please tell me your 9-digit patient ID, and describe the medical symptoms you are experiencing today."

Your goal is to collect a 9-digit alphanumeric patient ID, their primary symptoms, and their pain level (1-10).
Do not provide medical diagnoses.

MULTILINGUAL & HINGLISH ADAPTATION RULES:
1. LANGUAGE MIRRORING: Detect the language or dialect used by the patient (English or Hinglish / Hindi code-switching). 
2. If the patient speaks Hinglish (e.g., "mujhe leg mein pain ho raha hai", "sar dard hai", "bahut critical hai"), gracefully respond and converse back in natural, empathetic Hinglish (e.g., "Main samajh sakta hoon, aapko kitni takleef hai...").
3. INTERNAL STANDARDIZATION: While conversing in the user's preferred language, ensure that all extracted symptoms passed into backend tools (`update_patient_record`, `escalate_to_human`) are translated and logged in professional medical English for hospital records.

MANDATORY WORKFLOW & RULES:
1. As soon as the patient provides their 9-digit ID, immediately execute the `lookup_patient_history` tool. If returning, greet them warmly referencing past history in their preferred language.
2. If the patient describes complex symptoms, consult uploaded clinic protocols using `consult_knowledge_base`.
3. MANDATORY TOOL EXECUTION: As soon as you receive the pain level, immediately invoke `update_patient_record` or `escalate_to_human`. Do not chat further after pain level is given.
4. If pain level is 9-10 or severe/unbearable red-flag symptoms are mentioned, immediately execute `escalate_to_human`.
"""

GREETING_TEXT = "Hello, this is the MediTriage automated assistant. Please tell me your 9-digit patient ID, and describe the medical symptoms you are experiencing today."

async def run_agent():
    uri = "wss://agents.assemblyai.com/v1/ws"
    headers = {"Authorization": f"Bearer {os.environ['ASSEMBLYAI_API_KEY']}"}
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    mic = Mic()
    speaker = Speaker()
    session_transcript = []
    
    async with websockets.connect(uri, additional_headers=headers, ssl=ssl_context) as ws:
        session_config = {
            "type": "session.update",
            "session": {
                "system_prompt": SYSTEM_PROMPT,
                "greeting": GREETING_TEXT,
                "output": {"voice": "ivy"},
                "tools": [
                    {
                        "type": "function",
                        "name": "lookup_patient_history",
                        "description": "Look up previous patient records and history using their 9-digit ID.",
                        "parameters": LookupPatientHistory.model_json_schema()
                    },
                    {
                        "type": "function",
                        "name": "consult_knowledge_base",
                        "description": "Search uploaded clinical guidelines and protocols for symptom evaluation.",
                        "parameters": ConsultKnowledgeBase.model_json_schema()
                    },
                    {
                        "type": "function",
                        "name": "update_patient_record",
                        "description": "Save the patient's intake data to the EHR system.",
                        "parameters": PatientIntakeData.model_json_schema()
                    },
                    {
                        "type": "function",
                        "name": "check_clinic_hours",
                        "description": "Look up the clinic's operating hours for a specific day.",
                        "parameters": CheckClinicHours.model_json_schema()
                    },
                    {
                        "type": "function",
                        "name": "escalate_to_human",
                        "description": "Transfer the call to live nurse for severe pain or critical emergencies.",
                        "parameters": EscalateToHuman.model_json_schema()
                    }
                ]
            }
        }
        await ws.send(json.dumps(session_config))
        
        print("\n" + "="*50)
        print("🚀 MediTriage Agent Connected (Multilingual Hinglish Suite Active)")
        print("="*50)

        async def send_audio():
            await asyncio.sleep(1.5)
            mic.start()
            while True:
                try:
                    data = mic.queue.get_nowait()
                    if data:
                        payload = {"type": "input.audio", "audio": base64.b64encode(data).decode('utf-8')}
                        await ws.send(json.dumps(payload))
                except queue.Empty:
                    pass
                await asyncio.sleep(0.01)

        async def receive_events():
            async for message in ws:
                event = json.loads(message)
                event_type = event.get("type")
                
                if event_type == "session.error":
                    print(f"\n[FATAL SERVER ERROR]: {event.get('message')}")
                    os._exit(1)
                elif event_type == "reply.audio":
                    speaker.play(base64.b64decode(event["data"]))
                elif event_type == "transcript.user":
                    text = event.get('text', '')
                    print(f"\n[PATIENT]: {text}")
                    session_transcript.append(f"Patient: {text}")
                elif event_type == "transcript.agent":
                    text = event.get('text', '')
                    print(f"\n[AGENT]: {text}")
                    session_transcript.append(f"Agent: {text}")
                elif event_type == "input.speech.started":
                    speaker.flush_and_restart()
                    print("\n[-- PATIENT BARGED IN, FLUSHING AUDIO --]")
                elif event_type == "tool.call":
                    tool_call_id = event["call_id"]
                    tool_name = event["name"]
                    arguments = event["arguments"] 
                    full_transcript_str = "\n".join(session_transcript)
                    
                    if tool_name == "lookup_patient_history":
                        p_id = arguments.get("patient_id")
                        print(f"\n[🔍 LONGITUDINAL MEMORY]: Querying history for ID: {p_id}")
                        result = get_patient_history(p_id)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        
                    elif tool_name == "consult_knowledge_base":
                        query = arguments.get("query")
                        print(f"\n[📖 RAG QUERY]: {query}")
                        result = query_knowledge_base(query)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        
                    elif tool_name == "update_patient_record":
                        print(f"\n[EHR & SAFETY AUDIT]: {json.dumps(arguments, indent=2)}")
                        result = update_patient_record(arguments, transcript_summary=full_transcript_str)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        print(f"\n[✅ SAFETY SUPERVISOR]: {result.get('safety_audit')}")
                        
                    elif tool_name == "check_clinic_hours":
                        day = arguments.get("day_of_week", "Monday")
                        result = get_clinic_hours(day)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        
                    elif tool_name == "escalate_to_human":
                        print(f"\n[🚨 EMERGENCY ESCALATION & SMS]: {json.dumps(arguments, indent=2)}")
                        result = escalate_to_human(arguments, transcript_summary=full_transcript_str)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        print("\n[🚨 SAFETY SUPERVISOR]: Emergency routing and full transcript audit confirmed.")

        await asyncio.gather(send_audio(), receive_events())

if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\nSession ended by user.")
        import sys
        sys.exit(0)