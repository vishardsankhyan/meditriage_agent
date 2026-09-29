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
from db import update_patient_record, escalate_to_human, get_clinic_hours, get_patient_history, query_knowledge_base, check_doctor_intercom_db, log_live_utterance, register_active_session, close_active_session
from schemas import PatientIntakeData, CheckClinicHours, EscalateToHuman, LookupPatientHistory, ConsultKnowledgeBase, CheckDoctorIntercom

load_dotenv()

SYSTEM_PROMPT = """You are the receptionist and triage assistant for the MediTriage Medical Clinic. 
You must start the conversation by saying EXACTLY: "Hello, this is the MediTriage automated assistant. Please tell me your 9-digit patient UID, and describe the medical symptoms you are experiencing today."

Your goal is to collect a strict 9-digit alphanumeric patient ID, their primary symptoms, and their pain level (1-10).
STRICT VALIDATION: If the patient provides a patient ID that is NOT 9 digits long, politely ask them to repeat or verify their exact 9-digit ID before proceeding.
Do not provide medical diagnoses.

🚨 HIGHEST PRIORITY DOCTOR WHISPER OVERRIDE PROTOCOL:
1. On EVERY turn after the patient provides their ID, you MUST call `check_doctor_intercom`.
2. IF `check_doctor_intercom` returns `"CRITICAL_ALERT": "DOCTOR_WHISPER_INTERRUPTION"`, this overrides everything else! You MUST immediately take the text inside `"EXACT_PHRASE_TO_SPEAK_OUT_LOUD"` and **speak it out loud** to the patient using your voice right now.
"""

GREETING_TEXT = "Hello, this is the MediTriage automated assistant. Please tell me your 9-digit patient UID, and describe the medical symptoms you are experiencing today."

async def run_agent():
    uri = "wss://agents.assemblyai.com/v1/ws"
    headers = {"Authorization": f"Bearer {os.environ['ASSEMBLYAI_API_KEY']}"}
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    mic = Mic()
    speaker = Speaker()
    session_transcript = []
    
    current_session_id = f"CALL_{os.urandom(2).hex().upper()}"
    register_active_session(current_session_id)
    active_patient_id = [current_session_id]
    intake_completed = [False]
    
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
                        "description": "Look up previous patient records using their 9-digit ID.",
                        "parameters": LookupPatientHistory.model_json_schema()
                    },
                    {
                        "type": "function",
                        "name": "check_doctor_intercom",
                        "description": "Check if the on-call physician has sent a message that you must speak out loud to the patient.",
                        "parameters": CheckDoctorIntercom.model_json_schema()
                    },
                    {
                        "type": "function",
                        "name": "consult_knowledge_base",
                        "description": "Search uploaded clinical guidelines and protocols.",
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
                        "description": "Look up clinic operating hours.",
                        "parameters": CheckClinicHours.model_json_schema()
                    },
                    {
                        "type": "function",
                        "name": "escalate_to_human",
                        "description": "Transfer the call to a live nurse for severe emergencies.",
                        "parameters": EscalateToHuman.model_json_schema()
                    }
                ]
            }
        }
        await ws.send(json.dumps(session_config))
        
        print("\n" + "="*50)
        print(f"🚀 MediTriage Agent Connected [Session ID: {current_session_id}]")
        print("="*50)

        async def send_audio():
            await asyncio.sleep(1.5)
            mic.start()
            while True:
                if intake_completed[0]:
                    await asyncio.sleep(1)
                    continue
                try:
                    data = mic.queue.get_nowait()
                    if data:
                        payload = {"type": "input.audio", "audio": base64.b64encode(data).decode('utf-8')}
                        await ws.send(json.dumps(payload))
                except queue.Empty:
                    pass
                await asyncio.sleep(0.01)

        async def receive_events():
            nonlocal current_session_id
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
                    log_live_utterance(active_patient_id[0], "Patient", text)
                elif event_type == "transcript.agent":
                    text = event.get('text', '')
                    print(f"\n[AGENT]: {text}")
                    session_transcript.append(f"Agent: {text}")
                    log_live_utterance(active_patient_id[0], "Agent", text)
                elif event_type == "input.speech.started":
                    speaker.flush_and_restart()
                    print("\n[-- PATIENT BARGED IN, FLUSHING AUDIO --]")
                elif event_type == "tool.call":
                    tool_call_id = event["call_id"]
                    tool_name = event["name"]
                    arguments = event["arguments"] 
                    full_transcript_str = "\n".join(session_transcript)
                    
                    if tool_name == "lookup_patient_history":
                        p_id = arguments.get("patient_id", "").strip()
                        if len(p_id) != 9:
                            print(f"\n[⚠️ 9-DIGIT VALIDATION WARNING]: Invalid UID length received: '{p_id}' ({len(p_id)} chars)")
                        if p_id:
                            close_active_session(current_session_id)
                            current_session_id = p_id
                            register_active_session(current_session_id)
                            active_patient_id[0] = p_id
                        print(f"\n[🔍 LONGITUDINAL MEMORY]: Querying history for ID: {p_id}")
                        result = get_patient_history(p_id)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        
                    elif tool_name == "check_doctor_intercom":
                        if intake_completed[0]:
                            await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps({"CRITICAL_ALERT": "NONE"})}))
                            continue
                        p_id = arguments.get("patient_id")
                        if p_id and p_id != active_patient_id[0]:
                            close_active_session(current_session_id)
                            current_session_id = p_id
                            register_active_session(current_session_id)
                            active_patient_id[0] = p_id
                        result_str = check_doctor_intercom_db(active_patient_id[0])
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": result_str}))
                        
                    elif tool_name == "consult_knowledge_base":
                        query = arguments.get("query")
                        result = query_knowledge_base(query)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        
                    elif tool_name == "update_patient_record":
                        intake_completed[0] = True
                        p_id = arguments.get("patient_id")
                        if p_id:
                            active_patient_id[0] = p_id
                        result = update_patient_record(arguments, transcript_summary=full_transcript_str)
                        close_active_session(active_patient_id[0])
                        close_active_session(current_session_id)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        
                    elif tool_name == "check_clinic_hours":
                        day = arguments.get("day_of_week", "Monday")
                        result = get_clinic_hours(day)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))
                        
                    elif tool_name == "escalate_to_human":
                        intake_completed[0] = True
                        p_id = arguments.get("patient_id")
                        if p_id:
                            active_patient_id[0] = p_id
                        result = escalate_to_human(arguments, transcript_summary=full_transcript_str)
                        close_active_session(active_patient_id[0])
                        close_active_session(current_session_id)
                        await ws.send(json.dumps({"type": "tool.result", "call_id": tool_call_id, "result": json.dumps(result)}))

        await asyncio.gather(send_audio(), receive_events())

if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\nSession ended by user.")
        import sys
        sys.exit(0)