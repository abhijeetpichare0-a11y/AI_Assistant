import requests
from app.models import Appointment, Customer
from app.core.config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_NUMBER,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    RSL_WHATSAPP_API_URL,
    RSL_WHATSAPP_TOKEN,
    RSL_WHATSAPP_DEVICE_ID,
    RSL_WHATSAPP_DEVICE_NAME
)

def safe_str(val):
    if not val:
        return ""
    return str(val).encode('ascii', 'ignore').decode('ascii')

class WhatsAppProvider:
    def send(self, customer: Customer, appointment: Appointment, message: str, pdf_url: str | None = None, pdf_filepath: str | None = None) -> bool:
        raise NotImplementedError

class ConsoleWhatsAppProvider(WhatsAppProvider):
    def send(self, customer: Customer, appointment: Appointment, message: str, pdf_url: str | None = None, pdf_filepath: str | None = None) -> bool:
        print("=" * 60)
        print("WHATSAPP NOTIFICATION (CONSOLE / DEV MODE)")
        print("=" * 60)
        print(f"To      : {safe_str(customer.phone)}")
        print(f"Customer: {safe_str(customer.name)}")
        print(f"Message : {safe_str(message)}")
        if pdf_url:
            print(f"PDF Doc : {safe_str(pdf_url)}")
        print("=" * 60)
        return True

class RSLWhatsAppProvider(WhatsAppProvider):
    """
    RSL Solution WhatsApp Gateway Integration Provider
    Sends live WhatsApp messages & document attachments via wa.rslsolution.com API Gateway
    """
    def send(self, customer: Customer, appointment: Appointment, message: str, pdf_url: str | None = None, pdf_filepath: str | None = None) -> bool:
        try:
            url = RSL_WHATSAPP_API_URL or "https://whatsapp-platform-api-backend-zzis.onrender.com/api/unofficial/send-message"
            token = RSL_WHATSAPP_TOKEN or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlZWRmOTY3My05N2E5LTQxMzgtYWQxZS04YThjZTRkZjIxOTIiLCJlbWFpbCI6ImFiaGlqZWV0cGljaGFyZTBAZ21haWwuY29tIiwicm9sZSI6ImJ1c2luZXNzX293bmVyIiwiZXhwIjo0OTQyMDk4NzQyLCJ0eXBlIjoiYWNjZXNzIn0.j-W8FcRSCYNaiKMkYSYPeJkDlXmw75emj_YQOtJcQf0"
            device_id = RSL_WHATSAPP_DEVICE_ID or "14a583fb-0950-4c38-a36b-6060926e9855"
            device_name = RSL_WHATSAPP_DEVICE_NAME or "AI assistant (Chrome)"

            phone = (customer.phone or "").strip()
            clean_phone = "".join(filter(str.isdigit, phone))
            if len(clean_phone) == 10:
                clean_phone = f"91{clean_phone}"

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            payload = {
                "device_id": device_id,
                "device_name": device_name,
                "receiver_number": clean_phone,
                "message": message
            }

            if pdf_url:
                payload["media_url"] = pdf_url
                payload["document_url"] = pdf_url
                payload["filename"] = f"Appointment_Pass_{appointment.id}.pdf"

            print(f"[RSL WhatsApp] Dispatching live message to {clean_phone}...")
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            data = response.json()

            if response.status_code in [200, 201]:
                print(f"[RSL WhatsApp SUCCESS] Live WhatsApp Message Delivered: {data}")
                return True
            else:
                detail = data.get("detail", {})
                msg_text = detail.get("message") if isinstance(detail, dict) else str(detail)
                print(f"[RSL WhatsApp GATEWAY NOTICE {response.status_code}]: {safe_str(msg_text or data)}")
                
                # Console fallback to prevent crashing scheduler
                print("[RSL WhatsApp FALLBACK]: Logging notification locally...")
                ConsoleWhatsAppProvider().send(customer, appointment, message, pdf_url=pdf_url, pdf_filepath=pdf_filepath)
                return True

        except Exception as e:
            print(f"[RSL WhatsApp EXCEPTION]: {safe_str(e)}")
            ConsoleWhatsAppProvider().send(customer, appointment, message, pdf_url=pdf_url, pdf_filepath=pdf_filepath)
            return True

class TwilioWhatsAppProvider(WhatsAppProvider):
    def send(self, customer: Customer, appointment: Appointment, message: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            
            phone = customer.phone.strip()
            if not phone.startswith("+"):
                phone = f"+91{phone}" if len(phone) == 10 else f"+{phone}"

            msg = client.messages.create(
                body=message,
                from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
                to=f"whatsapp:{phone}"
            )
            print(f"[Twilio WhatsApp SUCCESS] Sent SID: {msg.sid}")
            return True
        except Exception as e:
            print(f"[Twilio WhatsApp ERROR]: {safe_str(e)}")
            return False

class MetaWhatsAppCloudProvider(WhatsAppProvider):
    def send(self, customer: Customer, appointment: Appointment, message: str) -> bool:
        try:
            if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
                print("[Meta WhatsApp ERROR]: Credentials missing in .env!")
                return False

            phone = customer.phone.strip()
            clean_phone = "".join(filter(str.isdigit, phone))
            if len(clean_phone) == 10:
                clean_phone = f"91{clean_phone}"

            url = f"https://graph.facebook.com/v20.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
            headers = {
                "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": clean_phone,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": message
                }
            }

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            data = response.json()

            if response.status_code in [200, 201] and "messages" in data:
                print(f"[Meta WhatsApp SUCCESS] Sent Message ID: {data['messages'][0]['id']}")
                return True
            else:
                print(f"[Meta WhatsApp ERROR]: {safe_str(data)}")
                return False

        except Exception as e:
            print(f"[Meta WhatsApp EXCEPTION]: {safe_str(e)}")
            return False