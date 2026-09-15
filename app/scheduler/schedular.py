from datetime import datetime
from app.database.database import SessionLocal
from app.models import Reminder
from app.services.notification_service import (
    send_appointment_reminder
)

def process_pending_reminders():
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