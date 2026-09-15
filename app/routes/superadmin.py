from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database.database import get_db
from app.models.user import User
from app.models.business import Business
from app.models.customer import Customer
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.staff import Staff
from app.routes.auth import require_superadmin

router = APIRouter(
    prefix="/superadmin",
    tags=["Superadmin Master Operations"]
)


@router.get("/dashboard")
def get_superadmin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    total_users = db.query(User).count()
    total_owners = db.query(User).filter(User.role == "owner").count()
    total_customers_registered = db.query(User).filter(User.role == "user").count()
    total_businesses = db.query(Business).count()
    total_appointments = db.query(Appointment).count()
    total_services = db.query(Service).filter(Service.is_active == True).count()
    total_staff = db.query(Staff).filter(Staff.is_active == True).count()
    total_customer_profiles = db.query(Customer).count()

    recent_users = db.query(User).order_by(User.created_at.desc()).limit(10).all()

    return {
        "superadmin": {
            "username": current_user.username,
            "phone": current_user.phone,
            "role": current_user.role
        },
        "metrics": {
            "total_users": total_users,
            "total_owners": total_owners,
            "total_user_accounts": total_customers_registered,
            "total_businesses": total_businesses,
            "total_appointments": total_appointments,
            "total_services": total_services,
            "total_staff": total_staff,
            "total_customer_profiles": total_customer_profiles
        },
        "recent_users": [
            {
                "id": u.id,
                "username": u.username,
                "phone": u.phone,
                "role": u.role,
                "business_id": u.business_id,
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else ""
            }
            for u in recent_users
        ]
    }


@router.get("/users")
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    res = []
    for u in users:
        biz_name = "N/A"
        if u.business_id:
            biz = db.query(Business).filter(Business.id == u.business_id).first()
            if biz: biz_name = biz.name

        res.append({
            "id": u.id,
            "username": u.username,
            "phone": u.phone,
            "role": u.role,
            "business_id": u.business_id,
            "business_name": biz_name,
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else ""
        })
    return res


@router.get("/businesses")
def get_all_businesses_master(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    businesses = db.query(Business).order_by(Business.created_at.desc()).all()
    res = []
    for b in businesses:
        appts_count = db.query(Appointment).filter(Appointment.business_id == b.id).count()
        services_count = db.query(Service).filter(Service.business_id == b.id, Service.is_active == True).count()
        staff_count = db.query(Staff).filter(Staff.business_id == b.id, Staff.is_active == True).count()
        cust_count = db.query(Customer).filter(Customer.business_id == b.id).count()

        res.append({
            "id": b.id,
            "name": b.name,
            "category": b.category,
            "owner_name": b.owner_name,
            "phone": b.phone,
            "location": b.location,
            "operating_hours": b.operating_hours,
            "status": b.status,
            "metrics": {
                "appointments": appts_count,
                "services": services_count,
                "staff": staff_count,
                "customers": cust_count
            }
        })
    return res


@router.get("/customers")
def get_all_customers_master(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    customers = db.query(Customer).order_by(Customer.created_at.desc()).all()
    res = []
    for c in customers:
        biz_name = c.business.name if c.business else "N/A"
        appts_count = db.query(Appointment).filter(Appointment.customer_id == c.id).count()
        res.append({
            "id": c.id,
            "business_id": c.business_id,
            "business_name": biz_name,
            "name": c.name,
            "phone": c.phone,
            "email": c.email,
            "appointments_count": appts_count,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
        })
    return res


@router.get("/appointments")
def get_all_appointments_master(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    appts = db.query(Appointment).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.asc()).all()
    return [
        {
            "id": a.id,
            "business_id": a.business_id,
            "business_name": a.business.name if a.business else "N/A",
            "customer_name": a.customer.name if a.customer else "Guest",
            "customer_phone": a.customer.phone if a.customer else "",
            "service_name": a.service.name if a.service else a.event_type,
            "staff_name": a.staff.name if a.staff else "Unassigned",
            "event_type": a.event_type,
            "appointment_date": str(a.appointment_date),
            "appointment_time": str(a.appointment_time),
            "venue": a.venue,
            "guests": a.guests,
            "status": a.status,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else ""
        }
        for a in appts
    ]


@router.delete("/users/{user_id}")
def delete_user_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User account not found")
    if u.role == "superadmin":
        raise HTTPException(status_code=400, detail="Cannot delete superadmin account")

    db.delete(u)
    db.commit()
    return {"message": f"User account #{user_id} deleted successfully by Superadmin."}
