from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Appointment, Reminder

def create_appointment_reminders(
    appointment: Appointment,
    db: Session
):
    appointment_datetime = datetime.combine(
        appointment.appointment_date,
        appointment.appointment_time
    )

    reminder_24h = Reminder(
        business_id=appointment.business_id,
        appointment_id=appointment.id,
        reminder_type="24_hours",
        scheduled_at=appointment_datetime - timedelta(hours=24),
        status="pending"
    )

    reminder_2h = Reminder(
        business_id=appointment.business_id,
        appointment_id=appointment.id,
        reminder_type="2_hours",
        scheduled_at=appointment_datetime - timedelta(hours=2),
        status="pending"
    )

    reminder_1h = Reminder(
        business_id=appointment.business_id,
        appointment_id=appointment.id,
        reminder_type="1_hour",
        scheduled_at=appointment_datetime - timedelta(hours=1),
        status="pending"
    )

    reminder_10m = Reminder(
        business_id=appointment.business_id,
        appointment_id=appointment.id,
        reminder_type="10_minutes",
        scheduled_at=appointment_datetime - timedelta(minutes=10),
        status="pending"
    )

    reminders = [reminder_24h, reminder_2h, reminder_1h, reminder_10m]
    for r in reminders:
        db.add(r)

    db.commit()
    return reminders