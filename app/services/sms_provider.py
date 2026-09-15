import requests
from app.models import Appointment, Customer
from app.core.config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_SMS_NUMBER,
    FAST2SMS_API_KEY
)

def safe_str(val):
    if not val:
        return ""
    return str(val).encode('ascii', 'ignore').decode('ascii')

class SMSProvider:
    def send(self, customer: Customer, appointment: Appointment, message: str) -> bool:
        raise NotImplementedError

class ConsoleSMSProvider(SMSProvider):
    def send(self, customer: Customer, appointment: Appointment, message: str) -> bool:
        print("=" * 60)
        print("SMS NOTIFICATION (CONSOLE / DEV MODE)")
        print("=" * 60)
        print(f"To      : {safe_str(customer.phone)}")
        print(f"Customer: {safe_str(customer.name)}")
        print(f"Message : {safe_str(message)}")
        print("=" * 60)
        return True

class TwilioSMSProvider(SMSProvider):
    def send(self, customer: Customer, appointment: Appointment, message: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            msg = client.messages.create(
                body=message,
                from_=TWILIO_SMS_NUMBER,
                to=customer.phone
            )
            print(f"[Twilio SMS SUCCESS] Sent SID: {msg.sid}")
            return True
        except Exception as e:
            print(f"[Twilio SMS ERROR]: {safe_str(e)}")
            return False

class Fast2SMSProvider(SMSProvider):
    def send(self, customer: Customer, appointment: Appointment, message: str) -> bool:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {"authorization": FAST2SMS_API_KEY}
            payload = {
                "route": "q",
                "message": message,
                "language": "english",
                "flash": 0,
                "numbers": customer.phone
            }
            res = requests.post(url, headers=headers, data=payload)
            data = res.json()
            return data.get("return", False)
        except Exception as e:
            print(f"[Fast2SMS ERROR]: {safe_str(e)}")
            return False