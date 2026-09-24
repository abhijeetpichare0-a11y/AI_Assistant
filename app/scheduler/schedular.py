import os
from datetime import datetime
from app.database.database import SessionLocal
from app.models import Reminder
from app.services.notification_service import (
    send_appointment_reminder
)

# Disabled/stopped by default to stop all pending reminders
SCHEDULER_ACTIVE = os.getenv("REMINDER_SCHEDULER_ACTIVE", "false").lower() in ("true", "1", "yes")

def stop_reminder_scheduler():
    global SCHEDULER_ACTIVE
    SCHEDULER_ACTIVE = False

def start_reminder_scheduler():
    global SCHEDULER_ACTIVE
    SCHEDULER_ACTIVE = True

def is_reminder_scheduler_active():
    return SCHEDULER_ACTIVE

def process_pending_reminders():
    if not SCHEDULER_ACTIVE:
        return 0

    db = SessionLocal()
    processed_count = 0

    try:
        reminders = (
            db.query(Reminder)
            .filter(
                Reminder.status.in_(["pending", "failed"]),
                Reminder.scheduled_at <= datetime.now()
            )
            .all()
        )

        for reminder in reminders:
            try:
                appointment = reminder.appointment
                if not appointment:
                    continue

                customer = appointment.customer
                if not customer:
                    continue

                result = send_appointment_reminder(
                    customer,
                    appointment,
                    reminder.reminder_type
                )

                if result.get("sms") or result.get("whatsapp"):
                    reminder.status = "sent"
                    reminder.sent_at = datetime.now()
                    processed_count += 1
                else:
                    reminder.status = "failed"

            except Exception as error:
                print(f"Failed to process reminder {reminder.id}: {error}")
                reminder.status = "failed"

        db.commit()
        return processed_count

    finally:
        db.close()