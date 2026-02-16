#!/usr/bin/env python3
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import anthropic
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default-secret')

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
YOUR_PHONE_NUMBER = os.environ.get('YOUR_PHONE_NUMBER')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

conversations = {}

class ConversationManager:
    def __init__(self, caller_id):
        self.caller_id = caller_id
        self.attempt_count = 0
        self.conversation_history = []
        self.caller_questions = []

    def add_question(self, question):
        self.attempt_count += 1
        self.caller_questions.append(question)
        self.conversation_history.append({"role": "user", "content": question})

    def add_response(self, response):
        self.conversation_history.append({"role": "assistant", "content": response})

    def should_escalate(self):
        return self.attempt_count >= 3

    def get_summary(self):
        summary = f"Caller: {self.caller_id}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        for i, question in enumerate(self.caller_questions, 1):
            summary += f"Q{i}: {question}\n"
        return summary

class AIAgent:
    def answer_question(self, question, conversation_history=None):
        if not anthropic_client:
            return "I apologize, the AI system is not configured."
        
        system_prompt = "You are a professional phone assistant. Keep answers brief and conversational. Be friendly and professional."
        messages = conversation_history or []
        if not messages or messages[-1]["content"] != question:
            messages.append({"role": "user", "content": question})
        
        try:
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return "I apologize, I am having trouble right now."

ai_agent = AIAgent()

@app.route("/voice", methods=['GET', 'POST'])
def handle
cat > ai_phone_answering_system.py << 'EOF'
#!/usr/bin/env python3
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import anthropic
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default-secret')

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
YOUR_PHONE_NUMBER = os.environ.get('YOUR_PHONE_NUMBER')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

conversations = {}

class ConversationManager:
    def __init__(self, caller_id):
        self.caller_id = caller_id
        self.attempt_count = 0
        self.conversation_history = []
        self.caller_questions = []

    def add_question(self, question):
        self.attempt_count += 1
        self.caller_questions.append(question)
        self.conversation_history.append({"role": "user", "content": question})

    def add_response(self, response):
        self.conversation_history.append({"role": "assistant", "content": response})

    def should_escalate(self):
        return self.attempt_count >= 3

    def get_summary(self):
        summary = f"Caller: {self.caller_id}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        for i, question in enumerate(self.caller_questions, 1):
            summary += f"Q{i}: {question}\n"
        return summary

class AIAgent:
    def answer_question(self, question, conversation_history=None):
        if not anthropic_client:
            return "I apologize, the AI system is not configured."
        
        system_prompt = "You are a professional phone assistant. Keep answers brief and conversational. Be friendly and professional."
        messages = conversation_history or []
        if not messages or messages[-1]["content"] != question:
            messages.append({"role": "user", "content": question})
        
        try:
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return "I apologize, I am having trouble right now."

ai_agent = AIAgent()

@app.route("/voice", methods=['GET', 'POST'])
def handle_incoming_call():
    response = VoiceResponse()
    caller_id = request.values.get('From', 'Unknown')
    call_sid = request.values.get('CallSid', 'Unknown')
    
    if call_sid not in conversations:
        conversations[call_sid] = ConversationManager(caller_id)
    
    response.say("Thank you for calling. I am an AI assistant. What can I help you with?", voice='alice')
    gather = Gather(input='speech', action='/process_speech', speech_timeout='auto', language='en-US')
    response.append(gather)
    response.redirect('/voice')
    return str(response)

@app.route("/process_speech", methods=['POST'])
def process_speech():
    response = VoiceResponse()
    speech_result = request.values.get('SpeechResult', '').strip()
    call_sid = request.values.get('CallSid', 'Unknown')
    caller_id = request.values.get('From', 'Unknown')
    
    if call_sid not in conversations:
        conversations[call_sid] = ConversationManager(caller_id)
    
    conversation = conversations[call_sid]
    
    if not speech_result:
        response.say("I did not catch that. Please repeat.")
        response.redirect('/voice')
        return str(response)
    
    conversation.add_question(speech_result)
    
    if conversation.should_escalate():
        send_sms_notification(conversation)
        response.say("I am having trouble finding the answer. Let me take a message. Please speak after the tone.", voice='alice')
        response.record(action='/handle_voicemail', max_length=60, transcribe=True, transcribe_callback='/handle_transcription')
        return str(response)
    
    ai_answer = ai_agent.answer_question(speech_result, conversation.conversation_history)
    conversation.add_response(ai_answer)
    
    response.say(ai_answer, voice='alice')
    response.say("Anything else I can help with?", voice='alice')
    
    gather = Gather(input='speech', action='/process_speech', speech_timeout='auto', timeout=5)
    response.append(gather)
    response.say("Thank you for calling!", voice='alice')
    response.hangup()
    return str(response)

@app.route("/handle_voicemail", methods=['POST'])
def handle_voicemail():
    response = VoiceResponse()
    response.say("Thank you. Someone will call you back soon. Goodbye!", voice='alice')
    response.hangup()
    return str(response)

@app.route("/handle_transcription", methods=['POST'])
def handle_transcription():
    call_sid = request.values.get('CallSid', 'Unknown')
    transcription = request.values.get('TranscriptionText', '')
    if call_sid in conversations:
        send_sms_with_voicemail(conversations[call_sid], transcription)
    return '', 200

def send_sms_notification(conversation):
    if not twilio_client or not YOUR_PHONE_NUMBER:
        print("Would send SMS:", conversation.get_summary())
        return
    try:
        twilio_client.messages.create(
            body=f"AI could not answer:\n\n{conversation.get_summary()}",
            from_=TWILIO_PHONE_NUMBER,
            to=YOUR_PHONE_NUMBER
        )
        print("SMS sent!")
    except Exception as e:
        print(f"SMS error: {e}")

def send_sms_with_voicemail(conversation, voicemail_text):
    if not twilio_client or not YOUR_PHONE_NUMBER:
        print("Voicemail:", voicemail_text)
        return
    try:
        twilio_client.messages.create(
            body=f"Voicemail:\n\n{conversation.get_summary()}\nMessage: {voicemail_text}",
            from_=TWILIO_PHONE_NUMBER,
            to=YOUR_PHONE_NUMBER
        )
        print("Voicemail SMS sent!")
    except Exception as e:
        print(f"SMS error: {e}")

@app.route("/status")
def status():
    return {"status": "running", "twilio": bool(twilio_client), "ai": bool(anthropic_client)}

@app.route("/")
def home():
    return {"message": "AI Phone System is running", "status": "ok"}
