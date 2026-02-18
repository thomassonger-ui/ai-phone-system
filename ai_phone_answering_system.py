from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
import anthropic
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Load environment variables from .env file
load_dotenv()

# Google Sheets setup
GOOGLE_SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', '1n5F3OjucrbrdOy4ZTrv3XQrC-gkBLeO8_1fMbth83ZA')
GOOGLE_CREDENTIALS_FILE = os.environ.get('GOOGLE_CREDENTIALS_FILE', 'worldteach-phone-597cdb70d3e8.json')
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS_JSON')  # For Render deployment

def get_sheets_client():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        # On Render: use environment variable (handles private key line breaks correctly)
        if GOOGLE_CREDENTIALS_JSON:
            import json
            info = json.loads(GOOGLE_CREDENTIALS_JSON)
            # Fix private key line breaks in case they got escaped
            if 'private_key' in info:
                info['private_key'] = info['private_key'].replace('\\n', '\n')
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            # Local: use the JSON file directly
            creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Google Sheets connection error: {e}")
        return None

def log_to_sheets(caller_id, call_type, conversation_text, voicemail_text=''):
    try:
        client = get_sheets_client()
        if not client:
            return
        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1
        # Add header row if sheet is empty
        if sheet.row_count == 0 or sheet.cell(1, 1).value != 'Date':
            sheet.insert_row(['Date', 'Time', 'Caller Phone', 'Call Type', 'Conversation', 'Voicemail Transcript'], 1)
        now = datetime.now()
        row = [
            now.strftime('%Y-%m-%d'),
            now.strftime('%I:%M %p EST'),
            caller_id,
            call_type,
            conversation_text,
            voicemail_text
        ]
        sheet.append_row(row)
        print(f"Logged to Google Sheets: {call_type} from {caller_id}")
    except Exception as e:
        print(f"Google Sheets logging error: {e}")

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

# Your public server URL (e.g. from Railway, Render, Heroku, ngrok)
# Set this in your .env file as: BASE_URL=https://your-app-name.up.railway.app
BASE_URL = os.environ.get('BASE_URL', '').rstrip('/')

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID else None
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
conversations = {}

BUSINESS_KNOWLEDGE = """
WORLD TEACH PATHWAYS - AI CURRICULUM SYSTEMS ARCHITECT & COMPLIANCE STRATEGIST

WHO WE ARE:
We are AI Curriculum Systems Architects and Compliance Strategists specializing in education technology infrastructure and regulatory readiness.

SERVICES OFFERED:
- 1:1 Academic Consulting (GED, ESL, ELA, Real Estate, Workforce Programs)
- Curriculum Design & Instructional Systems Architecture
- AI-Governed Curriculum & Compliance Consulting
- LMS Setup & Integration (Canvas, Moodle, ProProfs)
- Accreditation & Regulatory Readiness Support
- Microlearning & Training Development for Organizations

We serve: individual learners, schools, training providers, and organizations

BUSINESS HOURS:
- Monday to Friday: 9 AM to 6 PM Eastern Time
- Limited Saturday availability by appointment
- AI answering service available 24/7

LOCATION:
- Fully online nationwide
- In-person consulting available in Central Florida by request

PRICING:
- Academic Consulting: Custom packages based on subject and frequency
- Curriculum & Compliance Consulting: Monthly retainer or project-based
- LMS & Compliance Systems: Scope provided after consultation
- Pricing is customized - discovery call recommended

HOW TO BOOK:
- Call for callback
- Submit inquiry via website
- Email: contact@worldteachpathways.com
- All inquiries reviewed within one business day

SPECIALIZATIONS:
- GED prep consulting
- ESL/ELA program development
- Real Estate exam prep systems
- Workforce curriculum architecture
- AI-driven instructional design
- Compliance and accreditation systems

WHO WE SERVE:
- High school students and adult learners (academic consulting)
- Education professionals and institutional clients (systems architecture)
- Schools and training organizations (compliance and LMS)

CANCELLATION POLICY:
24-hour notice required for consulting sessions. Late cancellations may be subject to fee.

FREE CONSULTATION:
Yes - short discovery consultation available to assess fit and scope

KEY DIFFERENTIATOR:
We specialize in AI-governed curriculum systems and compliance strategy for education providers
"""

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

    def get_full_conversation(self):
        return "\n".join(self.caller_questions)

class AIAgent:
    def answer_question(self, question, conversation_history=None):
        if not anthropic_client:
            return "I apologize, our system is having trouble right now."

        system_prompt = f"""You are a professional receptionist for World Teach Pathways, an AI Curriculum Systems Architecture and Compliance Strategy firm.

IMPORTANT - USE THIS BUSINESS INFORMATION TO ANSWER QUESTIONS:
{BUSINESS_KNOWLEDGE}

Communication Guidelines:
- Keep answers natural, conversational, and brief (perfect for phone)
- Speak like a real person - warm, professional, and knowledgeable
- Use the business information above to give accurate answers
- Emphasize we're AI Curriculum Systems Architects and Compliance Strategists
- If asked about something not in the knowledge base, say: "That's a great question. Let me have one of our strategists call you back with details."
- IMPORTANT: End each response naturally. Only ask a follow-up question if it makes sense in context. For example, after answering about services you might ask "Would you like to schedule a free discovery call?" but do NOT robotically add "Is there anything else I can help you with?" every single time. Keep it conversational and natural.

For appointments/consultations:
- Be enthusiastic: "I'd love to help you schedule a consultation with our team!"
- Mention free discovery consultation when relevant
- Ask: "What day works best for you?" then "Morning or afternoon?"
- Ask what they're interested in: "Are you looking for curriculum architecture, compliance strategy, or academic consulting?"
- Get their phone number
- Confirm: "Perfect! One of our strategists will call you at [number] to discuss your [service] needs."

For pricing questions:
- Explain pricing is customized based on scope and needs
- Recommend a free discovery call to discuss specific pricing
- Mention we work with both individuals and institutions

For services questions:
- Emphasize our expertise in AI-governed curriculum systems
- Highlight compliance and accreditation support
- Mention LMS integration capabilities

For hours:
- We're available Monday through Friday, 9 AM to 6 PM Eastern
- Limited Saturday availability by appointment

Always be helpful, accurate, professional, and use the information provided above."""

        messages = conversation_history or []
        if not messages or messages[-1]["content"] != question:
            messages.append({"role": "user", "content": question})

        try:
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=350,
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
    # FIX: Use absolute URL so Twilio can find your server
    gather = Gather(input='speech', action=BASE_URL + '/process_speech', speech_timeout='auto', language='en-US')
    response.append(gather)
    response.redirect(BASE_URL + '/voice')
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
        # FIX: Use absolute URL
        response.redirect(BASE_URL + '/voice')
        return str(response)
    conversation.add_question(speech_result)

    is_appointment_request = any(word in speech_result.lower() for word in ['appointment', 'schedule', 'meeting', 'book', 'available', 'consultation', 'speak with', 'talk to'])

    if conversation.should_escalate():
        if is_appointment_request or any(word in q.lower() for q in conversation.caller_questions for word in ['appointment', 'schedule', 'consultation']):
            send_appointment_email(conversation)
            response.say("Perfect! I have all your information. One of our strategists will call you shortly to discuss your needs. Thanks for calling!", voice='Google.en-US-Neural2-F')
        else:
            send_email_notification(conversation)
            response.say("Let me take your information and someone from our team will get back to you soon.", voice='Google.en-US-Neural2-F')
            # FIX: Use absolute URLs for voicemail action and transcription callback
            response.record(
                action=BASE_URL + '/handle_voicemail',
                max_length=60,
                transcribe=True,
                transcribe_callback=BASE_URL + '/handle_transcription'
            )
            return str(response)
        response.hangup()
        return str(response)

    ai_answer = ai_agent.answer_question(speech_result, conversation.conversation_history)
    conversation.add_response(ai_answer)
    response.say(ai_answer, voice='Google.en-US-Neural2-F', language='en-US')
    # Let Claude's response end naturally - no robotic follow-up phrase added
    gather = Gather(input='speech', action=BASE_URL + '/process_speech', speech_timeout='auto', timeout=6)
    response.append(gather)
    response.say("Thanks for calling World Teach Pathways! Have a great day!", voice='Google.en-US-Neural2-F')
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

def send_email(subject, body, conversation):
    """Helper to send email - handles connection properly and closes on error."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD or not NOTIFICATION_EMAIL:
        print("Email not configured - check GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFICATION_EMAIL in .env")
        return
    server = None
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = NOTIFICATION_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        # FIX: Use context-safe server handling so connection always closes
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Email error: {e}")
    finally:
        # FIX: Always close the SMTP connection, even if an error occurred
        if server:
            try:
                server.quit()
            except Exception:
                pass

def send_appointment_email(conversation):
    log_to_sheets(conversation.caller_id, 'Consultation Request', conversation.get_full_conversation())
    body = "CONSULTATION REQUEST\n"
    body += "=" * 50 + "\n\n"
    body += "Caller Phone: " + conversation.caller_id + "\n"
    body += "Call Time: " + datetime.now().strftime('%Y-%m-%d %I:%M %p EST') + "\n\n"
    body += "CONVERSATION:\n"
    body += "-" * 50 + "\n"
    body += conversation.get_full_conversation() + "\n"
    body += "-" * 50 + "\n\n"
    body += "ACTION REQUIRED:\n"
    body += "Call " + conversation.caller_id + " to discuss their consultation needs.\n"
    send_email("NEW CONSULTATION REQUEST - World Teach Pathways", body, conversation)

def send_email_notification(conversation):
    log_to_sheets(conversation.caller_id, 'Inquiry', conversation.get_full_conversation())
    body = "New inquiry:\n\n" + conversation.get_summary()
    send_email("World Teach Pathways - Inquiry", body, conversation)

def send_email_with_voicemail(conversation, voicemail_text):
    log_to_sheets(conversation.caller_id, 'Voicemail', conversation.get_full_conversation(), voicemail_text)
    body = "New voicemail:\n\n" + conversation.get_summary() + "\nMessage: " + voicemail_text
    send_email("World Teach Pathways - New Voicemail", body, conversation)

@app.route("/status")
def status():
    return {"status": "running", "base_url": BASE_URL or "NOT SET - add BASE_URL to .env"}

@app.route("/")
def home():
    return {"message": "World Teach Pathways - AI Curriculum Systems & Compliance Strategy"}
