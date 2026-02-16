from dotenv import load_dotenv
import os

load_dotenv()

print("Environment variables loaded:")
print(f"TWILIO_ACCOUNT_SID: {os.environ.get('TWILIO_ACCOUNT_SID')}")
print(f"TWILIO_AUTH_TOKEN: {'***' + os.environ.get('TWILIO_AUTH_TOKEN', '')[-4:] if os.environ.get('TWILIO_AUTH_TOKEN') else 'NOT SET'}")
print(f"TWILIO_PHONE_NUMBER: {os.environ.get('TWILIO_PHONE_NUMBER')}")
print(f"YOUR_PHONE_NUMBER: {os.environ.get('YOUR_PHONE_NUMBER')}")

# Test Twilio connection
try:
    from twilio.rest import Client
    client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
    
    # Try to send a test SMS
    message = client.messages.create(
        body="Test message from AI phone system",
        from_=os.environ.get('TWILIO_PHONE_NUMBER'),
        to=os.environ.get('YOUR_PHONE_NUMBER')
    )
    print(f"\nSMS sent successfully! Message SID: {message.sid}")
except Exception as e:
    print(f"\nSMS ERROR: {e}")
