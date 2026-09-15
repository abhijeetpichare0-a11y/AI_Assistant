from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.user import User
from app.models.customer import Customer
from app.models.appointment import Appointment
from app.routes.auth import require_user, get_current_user

router = APIRouter(
    prefix="/user",
    tags=["Customer / User Profile & History"]
)


@router.get("/profile")
def get_user_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Find customer record(s) associated with this user's phone number
    customers = db.query(Customer).filter(Customer.phone == current_user.phone).all()
    customer_ids = [c.id for c in customers]

    today = date.today()

    all_appointments = []
    if customer_ids:
        all_appointments = db.query(Appointment).filter(
            Appointment.customer_id.in_(customer_ids)
        ).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.asc()).all()

    upcoming_bookings = []
    previous_history = []

    for a in all_appointments:
        biz_name = a.business.name if a.business else "Business"
        service_name = a.service.name if a.service else a.event_type
        staff_name = a.staff.name if a.staff else (a.staff_id or "Not assigned")

        appt_dict = {
            "id": a.id,
            "business_id": a.business_id,
            "business_name": biz_name,
            "event_type": a.event_type,
            "service_name": service_name,
            "staff_name": staff_name,
            "appointment_date": str(a.appointment_date),
            "appointment_time": str(a.appointment_time),
            "venue": a.venue,
            "guests": a.guests,
            "status": a.status,
            "notes": a.notes,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else ""
        }

        if a.appointment_date >= today and a.status in ["confirmed", "pending", "rescheduled"]:
            upcoming_bookings.append(appt_dict)
        else:
            previous_history.append(appt_dict)

    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "phone": current_user.phone,
            "role": current_user.role,
            "created_at": current_user.created_at.strftime("%Y-%m-%d %H:%M") if current_user.created_at else ""
        },
        "metrics": {
            "total_bookings": len(all_appointments),
            "upcoming_count": len(upcoming_bookings),
            "previous_count": len(previous_history)
        },
        "upcoming_bookings": upcoming_bookings,
        "previous_history": previous_history
    }
