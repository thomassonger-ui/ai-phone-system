from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import anthropic
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default-secret')

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER')
YOUR_PHONE_NUMBER = os.environ.get('YOUR_PHONE_NUMBER')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')
NOTIFICATION_EMAIL = os.environ.get('NOTIFICATION_EMAIL')

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
        summary = "Caller: " + self.caller_id + "\n"
        summary += "Time: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n\n"
        for i, question in enumerate(self.caller_questions, 1):
            summary += "Q" + str(i) + ": " + question + "\n"
        return summary

class AIAgent:
    def answer_question(self, question, conversation_history=None):
        if not anthropic_client:
            return "I apologize, our system is having trouble right now."
        system_prompt = "You are a friendly receptionist for World Teach Pathways. Keep answers natural, conversational, and brief. Speak like a real person - warm, professional, and helpful."
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
            return "Sorry, I'm having a little trouble right now."

ai_agent = AIAgent()

@app.route("/voice", methods=['GET', 'POST'])
def handle_incoming_call():
    response = VoiceResponse()
    caller_id = request.values.get('From', 'Unknown')
    call_sid = request.values.get('CallSid', 'Unknown')
    if call_sid not in conversations:
        conversations[call_sid] = ConversationManager(caller_id)
    response.say("Hi! Thanks for calling World Teach Pathways. How can I help you today?", voice='Google.en-US-Neural2-F', language='en-US')
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
        response.say("Sorry, I didn't catch that. Could you repeat that?", voice='Google.en-US-Neural2-F')
        response.redirect('/voice')
        return str(response)
    conversation.add_question(speech_result)
    if conversation.should_escalate():
        send_email_notification(conversation)
        response.say("I want to make sure you get the best help. Let me take your message and someone will get back to you soon.", voice='Google.en-US-Neural2-F')
        response.record(action='/handle_voicemail', max_length=60, transcribe=True, transcribe_callback='/handle_transcription')
        return str(response)
    ai_answer = ai_agent.answer_question(speech_result, conversation.conversation_history)
    conversation.add_response(ai_answer)
    response.say(ai_answer, voice='Google.en-US-Neural2-F', language='en-US')
    response.say("Is there anything else I can help you with?", voice='Google.en-US-Neural2-F')
    gather = Gather(input='speech', action='/process_speech', speech_timeout='auto', timeout=5)
    response.append(gather)
    response.say("Thanks for calling! Have a great day!", voice='Google.en-US-Neural2-F')
    response.hangup()
    return str(response)

@app.route("/handle_voicemail", methods=['POST'])
def handle_voicemail():
    response = VoiceResponse()
    response.say("Thank you. We'll call you back as soon as possible. Goodbye!", voice='Google.en-US-Neural2-F')
    response.hangup()
    return str(response)

@app.route("/handle_transcription", methods=['POST'])
def handle_transcription():
    call_sid = request.values.get('CallSid', 'Unknown')
    transcription = request.values.get('TranscriptionText', '')
    if call_sid in conversations:
        send_email_with_voicemail(conversations[call_sid], transcription)
    return '', 200

def send_email_notification(conversation):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not NOTIFICATION_EMAIL:
        print("Email not configured")
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = NOTIFICATION_EMAIL
        msg['Subject'] = "World Teach Pathways - Caller Needs Assistance"
        body = "A caller needs assistance:\n\n" + conversation.get_summary()
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent!")
    except Exception as e:
        print("Email error:", e)

def send_email_with_voicemail(conversation, voicemail_text):
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not NOTIFICATION_EMAIL:
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = NOTIFICATION_EMAIL
        msg['Subject'] = "World Teach Pathways - New Voicemail"
        body = "New voicemail:\n\n" + conversation.get_summary() + "\nMessage: " + voicemail_text
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Voicemail email sent!")
    except Exception as e:
        print("Email error:", e)

@app.route("/status")
def status():
    return {"status": "running"}

@app.route("/")
def home():
    return {"message": "World Teach Pathways Phone System"}
