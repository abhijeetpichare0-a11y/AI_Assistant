from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models import Reminder
from app.schemas.reminder import ReminderResponse


router = APIRouter(
    prefix="/reminders",
    tags=["Reminders"]
)


@router.get(
    "/",
    response_model=list[ReminderResponse]
)
def get_all_reminders(
    business_id: int | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(Reminder)
    if business_id:
        query = query.filter(Reminder.business_id == business_id)

    reminders = (
        query
        .order_by(Reminder.id.desc())
        .all()
    )
    return reminders

@router.get(
    "/appointment/{appointment_id}",
    response_model=list[ReminderResponse]
)
def get_appointment_reminders(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    reminders = (
        db.query(Reminder)
        .filter(
            Reminder.appointment_id == appointment_id
        )
        .all()
    )

    if not reminders:
        raise HTTPException(
            status_code=404,
            detail="No reminders found for this appointment"
        )

    return reminders


@router.get("/stats")
def get_reminder_stats(
    business_id: int | None = None,
    db: Session = Depends(get_db)
):
    from sqlalchemy import func
    query = db.query(Reminder.status, func.count(Reminder.id))
    if business_id:
        query = query.filter(Reminder.business_id == business_id)
    counts = dict(query.group_by(Reminder.status).all())
    total_query = db.query(func.count(Reminder.id))
    if business_id:
        total_query = total_query.filter(Reminder.business_id == business_id)
    total = total_query.scalar() or 0
    return {
        "total": total,
        "pending": counts.get("pending", 0),
        "sent": counts.get("sent", 0),
        "paused": counts.get("paused", 0),
        "failed": counts.get("failed", 0)
    }


@router.delete("/pending")
def delete_pending_reminders(
    business_id: int | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(Reminder).filter(Reminder.status == "pending")
    if business_id:
        query = query.filter(Reminder.business_id == business_id)
    count = query.delete(synchronize_session=False)
    db.commit()
    return {
        "message": f"Successfully deleted {count} pending reminders.",
        "deleted_count": count
    }