#!/usr/bin/env python3
import os, sys, re
from pathlib import Path

def validate_phone(phone):
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if cleaned.startswith('+') and 11 <= len(cleaned) <= 16:
        return cleaned
    elif cleaned.isdigit() and len(cleaned) == 10:
        return f"+1{cleaned}"
    return None

def validate_api_key(key, key_type):
    if not key or len(key) < 20: return False
    if key_type == "twilio_sid" and not key.startswith("AC"): return False
    if key_type == "anthropic" and not key.startswith("sk-ant-"): return False
    return True

def get_input(prompt, validator=None, error_msg="Invalid input"):
    while True:
        value = input(prompt).strip()
        if not value:
            print("❌ Required field.")
            continue
        if validator:
            validated = validator(value)
            if validated is None or validated is False:
                print(f"❌ {error_msg}")
                continue
            return validated if validated is not True else value
        return value

print("""
╔══════════════════════════════════════════════════════════════╗
║      AI PHONE ANSWERING SYSTEM - SETUP WIZARD              ║
╚══════════════════════════════════════════════════════════════╝

You'll need:
  • Twilio Account SID, Auth Token, and Phone Number
  • Your phone number (for SMS alerts)
  • Anthropic API key

Press Enter to continue...
""")
input()

print("\n" + "="*60)
print("STEP 1: Twilio Configuration")
print("="*60)
print("\n📱 Get from: https://console.twilio.com\n")

twilio_sid = get_input("Twilio Account SID (starts with 'AC'): ", lambda x: validate_api_key(x, "twilio_sid"), "Should start with 'AC'")
twilio_token = get_input("Twilio Auth Token: ", lambda x: len(x) >= 20, "Token too short")
twilio_phone = get_input("Twilio Phone Number (+12025551234): ", validate_phone, "Use format: +1234567890")

print(f"\n✅ Twilio: {twilio_phone}")

print("\n" + "="*60)
print("STEP 2: Your Phone Number")
print("="*60)
your_phone = get_input("\nYour Phone Number (+12025551234): ", validate_phone, "Invalid format")
print(f"✅ SMS to: {your_phone}")

print("\n" + "="*60)
print("STEP 3: Anthropic API Key")
print("="*60)
print("\n🤖 Get from: https://console.anthropic.com\n")
anthropic_key = get_input("Anthropic API Key (sk-ant-...): ", lambda x: validate_api_key(x, "anthropic"), "Should start with 'sk-ant-'")
print("✅ AI configured")

import secrets
flask_secret = secrets.token_urlsafe(32)

env_content = f"""TWILIO_ACCOUNT_SID={twilio_sid}
TWILIO_AUTH_TOKEN={twilio_token}
TWILIO_PHONE_NUMBER={twilio_phone}
YOUR_PHONE_NUMBER={your_phone}
ANTHROPIC_API_KEY={anthropic_key}
FLASK_SECRET_KEY={flask_secret}
"""

with open('.env', 'w') as f:
    f.write(env_content)

print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    ✅ SETUP COMPLETE!                        ║
╚══════════════════════════════════════════════════════════════╝

Configuration saved to .env

Next steps:
  1. pip3 install -r requirements.txt
  2. python3 ai_phone_answering_system.py
  3. Use ngrok: ngrok http 5000
  4. Configure Twilio webhook to: https://your-url/voice
  5. Test: Call {twilio_phone}
""")
