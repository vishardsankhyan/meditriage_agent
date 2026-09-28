# agent.py
import asyncio
import sys
import websockets
import json
import os
import base64
import ssl
import queue
from dotenv import load_dotenv
from audio import Mic, Speaker
from db import update_patient_record, escalate_to_human, get_clinic_hours
from schemas import PatientIntakeData, CheckClinicHours, EscalateToHuman

load_dotenv()

SYSTEM_PROMPT = """You are the receptionist and triage assistant for the MediTriage Medical Clinic. 
You must start the conversation by saying EXACTLY: "Hello, this is the MediTriage automated assistant. Please tell me your 9-digit patient ID, and describe the medical symptoms you are experiencing today."

Your goal is to collect a 9-digit alphanumeric patient ID, their primary symptoms, and their pain level (1-10).
Do not provide medical diagnoses.

ROUTING RULES:
1. If the patient asks about clinic hours, operating hours, schedule, or availability, execute the check_clinic_hours tool immediately to get the answer, tell them the clinic's hours, and then smoothly return to gathering their medical information.
2. If the patient reports a pain level of 9 or 10, or mentions critical symptoms (chest pain, severe bleeding, difficulty breathing), immediately execute the escalate_to_human tool.
3. If it is a standard non-emergency, once you have the ID, symptoms, and pain level, execute the update_patient_record tool.

After update_patient_record or escalate_to_human is successfully saved, verbally confirm the record with the patient and say a polite goodbye wishing them well."""

GREETING_TEXT = "Hello, this is the MediTriage automated assistant. Please tell me your 9-digit patient ID, and describe the medical symptoms you are experiencing today."

async def run_agent():
    uri = "wss://agents.assemblyai.com/v1/ws"
    headers = {"Authorization": f"Bearer {os.environ['ASSEMBLYAI_API_KEY']}"}
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    mic = Mic()
    speaker = Speaker()
    
    async with websockets.connect(uri, additional_headers=headers, ssl=ssl_context) as ws:
        session_config = {
            "type": "session.update",
            "session": {
                "system_prompt": SYSTEM_PROMPT,
                "greeting": GREETING_TEXT,
                "output": {
                    "voice": "ivy"
                },
                "tools": [
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
                        "description": "Transfer the call to a live nurse for severe pain or critical emergencies.",
                        "parameters": EscalateToHuman.model_json_schema()
                    }
                ]
            }
        }
        await ws.send(json.dumps(session_config))
        
        print("\n" + "="*50)
        print("🚀 MediTriage Agent Connected and Listening")
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
                    print(f"\n[FATAL SERVER ERROR]: {event.get('message')} (Code: {event.get('code')})")
                    os._exit(1)
                
                elif event_type == "reply.audio":
                    speaker.play(base64.b64decode(event["data"]))
                    
                elif event_type == "transcript.user":
                    print(f"\n[PATIENT]: {event.get('text', '')}")
                    
                elif event_type == "transcript.agent":
                    print(f"\n[AGENT]: {event.get('text', '')}")
                    
                elif event_type == "input.speech.started":
                    speaker.flush_and_restart()
                    print("\n[-- PATIENT BARGED IN, FLUSHING AUDIO --]")
                        
                elif event_type == "tool.call":
                    tool_call_id = event["call_id"]
                    tool_name = event["name"]
                    arguments = event["arguments"] 
                    
                    if tool_name == "update_patient_record":
                        print(f"\n[EHR UPDATE TRIGGERED]: {json.dumps(arguments, indent=2)}")
                        result = update_patient_record(arguments)
                        
                        # Send result back to server; let the agent speak completely naturally
                        await ws.send(json.dumps({
                            "type": "tool.result", 
                            "call_id": tool_call_id, 
                            "result": json.dumps(result)
                        }))
                        print("\n[SYSTEM]: Record saved successfully. Agent is speaking confirmation...")
                        
                    elif tool_name == "check_clinic_hours":
                        day = arguments.get("day_of_week", "Monday")
                        print(f"\n[CLINIC HOURS LOOKUP]: Checking hours for {day}")
                        result = get_clinic_hours(day)
                        await ws.send(json.dumps({
                            "type": "tool.result", 
                            "call_id": tool_call_id, 
                            "result": json.dumps(result)
                        }))
                        
                    elif tool_name == "escalate_to_human":
                        print(f"\n[🚨 ESCALATION TRIGGERED]: {json.dumps(arguments, indent=2)}")
                        result = escalate_to_human(arguments)
                        await ws.send(json.dumps({
                            "type": "tool.result", 
                            "call_id": tool_call_id, 
                            "result": json.dumps(result)
                        }))
                        print("\n[SYSTEM]: Escalation logged. Agent is transferring the call...")

        await asyncio.gather(send_audio(), receive_events())

if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\nSession ended by user.")
        sys.exit(0)