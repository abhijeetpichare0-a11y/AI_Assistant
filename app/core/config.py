import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
NOTIFICATION_MODE = os.getenv("NOTIFICATION_MODE", "TEST")

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "console")
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "rsl")

# RSL Solution WhatsApp Platform Credentials
RSL_WHATSAPP_API_URL = os.getenv("RSL_WHATSAPP_API_URL", "https://whatsapp-platform-api-backend-zzis.onrender.com/api/unofficial/send-message")
RSL_WHATSAPP_TOKEN = os.getenv("RSL_WHATSAPP_TOKEN", "")
RSL_WHATSAPP_DEVICE_ID = os.getenv("RSL_WHATSAPP_DEVICE_ID", "14a583fb-0950-4c38-a36b-6060926e9855")
RSL_WHATSAPP_DEVICE_NAME = os.getenv("RSL_WHATSAPP_DEVICE_NAME", "AI assistant (Chrome)")

# Twilio Credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_SMS_NUMBER = os.getenv("TWILIO_SMS_NUMBER", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

# Fast2SMS Credentials
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY", "")

# Meta / Facebook WhatsApp Cloud API Credentials
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")