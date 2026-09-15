from app.models import Appointment, Customer
from app.core.config import (
    SMS_PROVIDER,
    WHATSAPP_PROVIDER
)
from app.services.sms_provider import (
    ConsoleSMSProvider,
    TwilioSMSProvider,
    Fast2SMSProvider
)
from app.services.whatsapp_provider import (
    ConsoleWhatsAppProvider,
    TwilioWhatsAppProvider,
    MetaWhatsAppCloudProvider,
    RSLWhatsAppProvider
)

def get_sms_provider():
    provider = (SMS_PROVIDER or "console").lower()
    if provider == "console":
        return ConsoleSMSProvider()
    elif provider == "twilio":
        return TwilioSMSProvider()
    elif provider == "fast2sms":
        return Fast2SMSProvider()
    return ConsoleSMSProvider()

def get_whatsapp_provider():
    provider = (WHATSAPP_PROVIDER or "rsl").lower()
    if provider in ["rsl", "rsl_solution", "rsl_whatsapp"]:
        return RSLWhatsAppProvider()
    elif provider == "console":
        return ConsoleWhatsAppProvider()
    elif provider == "twilio":
        return TwilioWhatsAppProvider()
    elif provider in ["meta", "meta_cloud", "meta_whatsapp"]:
        return MetaWhatsAppCloudProvider()
    return RSLWhatsAppProvider()

def send_sms(customer: Customer, appointment: Appointment, message: str):
    provider = get_sms_provider()
    return provider.send(customer, appointment, message)

def send_whatsapp(customer: Customer, appointment: Appointment, message: str):
    provider = get_whatsapp_provider()
    return provider.send(customer, appointment, message)

def send_appointment_reminder(customer: Customer, appointment: Appointment, reminder_type: str):
    rem_text = reminder_type.replace('_', ' ')
    message = (
        f"Reminder ({rem_text}): "
        f"Hi {customer.name}, your {appointment.event_type} appointment "
        f"is scheduled for {appointment.appointment_date} at {appointment.appointment_time}. "
        f"Venue: {appointment.venue or 'Specified location'}."
    )

    sms_result = send_sms(customer, appointment, message)
    whatsapp_result = send_whatsapp(customer, appointment, message)

    return {
        "sms": sms_result,
        "whatsapp": whatsapp_result
    }