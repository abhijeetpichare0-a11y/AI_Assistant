from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database.database import get_db
from app.models.user import User
from app.models.business import Business
from app.models.service import Service
from app.models.staff import Staff
from app.models.rule import BusinessRule
from app.models.customer import Customer
from app.models.appointment import Appointment
from app.models.document import BusinessDocument
from app.models.business_hours import BusinessHours
from app.models.faq import BusinessFAQ
from app.routes.auth import require_owner
from app.agents.owner_agent import OwnerAgent
from app.services.document_parser import parse_and_save_uploaded_file
from app.services.ai_business_extractor import extract_business_profile_from_documents, DAYS_OF_WEEK
from app.schemas.document_setup import (
    DocumentExtractionResponse,
    BusinessSetupConfirmRequest
)
from app.schemas.owner import (
    BusinessOnboardRequest,
    BusinessUpdateRequest,
    ServiceCreateRequest,
    StaffCreateRequest,
    WorkingHoursUpdateRequest,
    MultiDayHoursUpdateRequest,
    DayHoursItem,
    BookingRulesUpdateRequest,
    OwnerChatRequest,
    OwnerChatResponse
)

router = APIRouter(
    prefix="/owner",
    tags=["Owner Dashboard & Management"]
)


def get_owner_business(current_user: User, db: Session) -> Business:
    if not current_user.business_id:
        # Check if a business matches phone
        biz = db.query(Business).filter(Business.phone == current_user.phone).first()
        if biz:
            current_user.business_id = biz.id
            db.commit()
            db.refresh(current_user)
            return biz
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No business registered for this owner account. Please complete onboarding."
        )
    biz = db.query(Business).filter(Business.id == current_user.business_id).first()
    if not biz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business record not found."
        )
    return biz


def ensure_default_business_hours(business_id: int, db: Session) -> List[BusinessHours]:
    existing = db.query(BusinessHours).filter(BusinessHours.business_id == business_id).all()
    if existing and len(existing) == 7:
        return existing

    existing_days = {h.day for h in existing}
    for day in DAYS_OF_WEEK:
        if day not in existing_days:
            is_open = (day != "Sunday")
            db.add(BusinessHours(
                business_id=business_id,
                day=day,
                opening_time="10:00",
                closing_time="20:00",
                is_open=is_open
            ))
    db.commit()
    return db.query(BusinessHours).filter(BusinessHours.business_id == business_id).all()


# -------------------------------------------------------------------
# 1. BUSINESS ONBOARDING (MANUAL & DOCUMENT-DRIVEN)
# -------------------------------------------------------------------
@router.post("/onboard")
def onboard_business(
    payload: BusinessOnboardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = Business(
        name=payload.name,
        category=payload.category,
        owner_name=current_user.username,
        phone=payload.phone or current_user.phone,
        services_text="",
        description=payload.description,
        location=payload.location,
        currency=payload.currency or "INR",
        operating_hours=payload.operating_hours or "10:00 AM - 08:00 PM",
        timezone=payload.timezone or "Asia/Kolkata",
        status="active"
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    current_user.business_id = biz.id
    db.commit()
    db.refresh(current_user)

    # Seed default rules
    default_rules = [
        ("min_notice_hours", "2", "Minimum advance notice required before booking"),
        ("max_advance_days", "30", "Maximum days in advance a customer can book"),
        ("cancellation_rules", "Free cancellation up to 2 hours before appointment", "Cancellation terms"),
        ("rescheduling_rules", "Reschedule up to 2 hours before appointment", "Rescheduling terms"),
        ("booking_buffer_mins", "15", "Buffer time between appointments"),
        ("max_group_size", "10", "Maximum group size per booking"),
        ("deposit_requirements", "None", "Deposit requirements for services"),
        ("late_arrival_rules", "15-minute grace period", "Grace period policy")
    ]
    for r_key, r_val, r_desc in default_rules:
        db.add(BusinessRule(business_id=biz.id, rule_key=r_key, rule_value=r_val, description=r_desc))
    db.commit()

    ensure_default_business_hours(biz.id, db)

    return {
        "message": f"🎉 Business '{biz.name}' onboarded successfully!",
        "business_id": biz.id,
        "name": biz.name
    }


@router.post("/setup/upload-documents", response_model=DocumentExtractionResponse)
async def upload_setup_documents(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    saved_doc_entries = []
    for upload in files:
        file_bytes = await upload.read()
        if not file_bytes:
            continue
        parsed = parse_and_save_uploaded_file(
            file_bytes=file_bytes,
            original_filename=upload.filename,
            owner_id=current_user.id
        )

        doc_record = BusinessDocument(
            business_id=current_user.business_id,
            owner_id=current_user.id,
            original_filename=parsed["original_filename"],
            file_type=parsed["file_type"],
            file_path=parsed["file_path"],
            file_size=parsed["file_size"],
            extracted_text=parsed["extracted_text"],
            processing_status=parsed["processing_status"],
            error_message=parsed["error_message"]
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)

        parsed["id"] = doc_record.id
        saved_doc_entries.append(parsed)

    if not saved_doc_entries:
        raise HTTPException(status_code=400, detail="No readable content found in uploaded document(s).")

    extraction = extract_business_profile_from_documents(saved_doc_entries)
    return extraction


@router.post("/setup/confirm")
def confirm_business_setup(
    payload: BusinessSetupConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = None
    if current_user.business_id:
        biz = db.query(Business).filter(Business.id == current_user.business_id).first()

    if not biz:
        biz = Business(
            name=payload.name,
            category=payload.category,
            owner_name=current_user.username,
            phone=payload.phone or current_user.phone,
            services_text="",
            description=payload.description,
            location=payload.location,
            currency=payload.currency or "INR",
            operating_hours="10:00 AM - 08:00 PM",
            timezone=payload.timezone or "Asia/Kolkata",
            status="active"
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)
        current_user.business_id = biz.id
        db.commit()
        db.refresh(current_user)
    else:
        biz.name = payload.name
        biz.category = payload.category
        if payload.phone:
            biz.phone = payload.phone
        if payload.description:
            biz.description = payload.description
        if payload.location:
            biz.location = payload.location
        if payload.currency:
            biz.currency = payload.currency
        db.commit()

    # Link uploaded documents to business
    if payload.document_ids:
        db.query(BusinessDocument).filter(
            BusinessDocument.id.in_(payload.document_ids),
            BusinessDocument.owner_id == current_user.id
        ).update({"business_id": biz.id}, synchronize_session=False)
        db.commit()

    # Save 7-day BusinessHours
    if payload.business_hours:
        db.query(BusinessHours).filter(BusinessHours.business_id == biz.id).delete()
        for h in payload.business_hours:
            db.add(BusinessHours(
                business_id=biz.id,
                day=h.day,
                opening_time=h.opening_time,
                closing_time=h.closing_time,
                is_open=h.is_open
            ))
        db.commit()
    else:
        ensure_default_business_hours(biz.id, db)

    # Save Services
    if payload.services:
        for s in payload.services:
            existing_s = db.query(Service).filter(
                Service.business_id == biz.id,
                Service.name.ilike(s.name.strip())
            ).first()
            if not existing_s:
                db.add(Service(
                    business_id=biz.id,
                    name=s.name.strip(),
                    category=s.category or "General",
                    price=float(s.price),
                    duration_minutes=int(s.duration_minutes),
                    description=s.description or "",
                    is_active=True
                ))
            else:
                existing_s.price = float(s.price)
                existing_s.duration_minutes = int(s.duration_minutes)
        db.commit()

    # Save Booking Rules
    default_rules = {
        "min_notice_hours": "2",
        "max_advance_days": "30",
        "cancellation_rules": "Free cancellation up to 2 hours before appointment",
        "rescheduling_rules": "Reschedule up to 2 hours before appointment",
        "booking_buffer_mins": "15",
        "max_group_size": "10",
        "deposit_requirements": "None",
        "late_arrival_rules": "15-minute grace period"
    }
    if payload.booking_rules:
        rule_map = {
            "min_notice_hours": str(payload.booking_rules.min_notice_hours),
            "max_advance_days": str(payload.booking_rules.max_advance_days),
            "cancellation_rules": payload.booking_rules.cancellation_rules,
            "rescheduling_rules": payload.booking_rules.rescheduling_rules,
            "booking_buffer_mins": str(payload.booking_rules.booking_buffer_mins),
            "max_group_size": str(payload.booking_rules.max_group_size),
            "deposit_requirements": payload.booking_rules.deposit_requirements,
            "late_arrival_rules": payload.booking_rules.late_arrival_rules,
        }
    else:
        rule_map = default_rules

    for r_key, r_val in rule_map.items():
        rule = db.query(BusinessRule).filter(BusinessRule.business_id == biz.id, BusinessRule.rule_key == r_key).first()
        if not rule:
            db.add(BusinessRule(business_id=biz.id, rule_key=r_key, rule_value=r_val))
        else:
            rule.rule_value = r_val
    db.commit()

    # Save FAQs
    if payload.faqs:
        for faq in payload.faqs:
            existing_faq = db.query(BusinessFAQ).filter(
                BusinessFAQ.business_id == biz.id,
                BusinessFAQ.question.ilike(faq.question.strip())
            ).first()
            if not existing_faq:
                db.add(BusinessFAQ(
                    business_id=biz.id,
                    question=faq.question.strip(),
                    answer=faq.answer.strip()
                ))
        db.commit()

    return {
        "message": f"🎉 Business '{biz.name}' successfully configured and live!",
        "business_id": biz.id,
        "name": biz.name,
        "services_count": len(payload.services or []),
        "documents_linked": len(payload.document_ids or [])
    }


@router.get("/documents")
def get_owner_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    docs = db.query(BusinessDocument).filter(
        (BusinessDocument.owner_id == current_user.id) |
        (BusinessDocument.business_id == current_user.business_id)
    ).order_by(BusinessDocument.uploaded_at.desc()).all()

    return [
        {
            "id": d.id,
            "original_filename": d.original_filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "processing_status": d.processing_status,
            "error_message": d.error_message,
            "uploaded_at": d.uploaded_at.strftime("%Y-%m-%d %H:%M") if d.uploaded_at else ""
        }
        for d in docs
    ]


# -------------------------------------------------------------------
# 2. BUSINESS OVERVIEW / DASHBOARD METRICS
# -------------------------------------------------------------------
@router.get("/dashboard")
def get_owner_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)

    today = date.today()

    today_appts = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.appointment_date == today
    ).order_by(Appointment.appointment_time.asc()).all()

    upcoming_appts = db.query(Appointment).filter(
        Appointment.business_id == biz.id,
        Appointment.appointment_date >= today
    ).order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).limit(10).all()

    total_services = db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).count()
    total_staff = db.query(Staff).filter(Staff.business_id == biz.id, Staff.is_active == True).count()
    total_customers = db.query(Customer).filter(Customer.business_id == biz.id).count()
    total_appointments = db.query(Appointment).filter(Appointment.business_id == biz.id).count()

    return {
        "business": {
            "id": biz.id,
            "name": biz.name,
            "category": biz.category,
            "owner_name": biz.owner_name,
            "status": biz.status,
            "operating_hours": biz.operating_hours,
            "phone": biz.phone,
            "location": biz.location
        },
        "metrics": {
            "today_appointments_count": len(today_appts),
            "total_appointments": total_appointments,
            "total_services": total_services,
            "total_staff": total_staff,
            "total_customers": total_customers
        },
        "today_appointments": [
            {
                "id": a.id,
                "customer_name": a.customer.name if a.customer else "Guest",
                "customer_phone": a.customer.phone if a.customer else "",
                "event_type": a.event_type,
                "date": str(a.appointment_date),
                "time": str(a.appointment_time),
                "venue": a.venue,
                "status": a.status
            }
            for a in today_appts
        ],
        "upcoming_appointments": [
            {
                "id": a.id,
                "customer_name": a.customer.name if a.customer else "Guest",
                "customer_phone": a.customer.phone if a.customer else "",
                "event_type": a.event_type,
                "date": str(a.appointment_date),
                "time": str(a.appointment_time),
                "venue": a.venue,
                "status": a.status
            }
            for a in upcoming_appts
        ]
    }


# -------------------------------------------------------------------
# 3. BUSINESS INFORMATION READ & UPDATE
# -------------------------------------------------------------------
@router.get("/business")
def get_business_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    return {
        "id": biz.id,
        "name": biz.name,
        "category": biz.category,
        "description": biz.description,
        "phone": biz.phone,
        "owner_name": biz.owner_name,
        "location": biz.location,
        "currency": biz.currency,
        "timezone": biz.timezone,
        "operating_hours": biz.operating_hours,
        "status": biz.status
    }


@router.put("/business")
def update_business_info(
    payload: BusinessUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    if payload.name: biz.name = payload.name
    if payload.category: biz.category = payload.category
    if payload.description: biz.description = payload.description
    if payload.phone: biz.phone = payload.phone
    if payload.location: biz.location = payload.location
    if payload.currency: biz.currency = payload.currency
    if payload.timezone: biz.timezone = payload.timezone
    if payload.operating_hours: biz.operating_hours = payload.operating_hours

    db.commit()
    db.refresh(biz)
    return {"message": "Business details updated successfully!", "business": get_business_info(db, current_user)}


# -------------------------------------------------------------------
# 4. SERVICES MANAGEMENT (CRUD)
# -------------------------------------------------------------------
@router.get("/services")
def list_owner_services(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    services = db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "duration_minutes": s.duration_minutes,
            "price": float(s.price or 0),
            "deposit_percentage": s.deposit_percentage,
            "required_resource_type": s.required_resource_type,
            "description": s.description
        }
        for s in services
    ]


@router.post("/services")
def add_owner_service(
    payload: ServiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    svc = Service(
        business_id=biz.id,
        name=payload.name,
        category=payload.category or biz.category,
        duration_minutes=payload.duration_minutes or 30,
        price=payload.price or 0.0,
        deposit_percentage=payload.deposit_percentage or 0,
        required_resource_type=payload.required_resource_type,
        description=payload.description,
        is_active=True
    )
    db.add(svc)

    # Update services_text in business table
    all_svc = db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).all()
    biz.services_text = ", ".join([s.name for s in all_svc] + [svc.name])

    db.commit()
    db.refresh(svc)
    return {"message": f"Service '{svc.name}' created successfully!", "id": svc.id}


@router.put("/services/{service_id}")
def update_owner_service(
    service_id: int,
    payload: ServiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    svc = db.query(Service).filter(Service.id == service_id, Service.business_id == biz.id).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    if payload.name: svc.name = payload.name
    if payload.category: svc.category = payload.category
    if payload.duration_minutes is not None: svc.duration_minutes = payload.duration_minutes
    if payload.price is not None: svc.price = payload.price
    if payload.deposit_percentage is not None: svc.deposit_percentage = payload.deposit_percentage
    if payload.required_resource_type is not None: svc.required_resource_type = payload.required_resource_type
    if payload.description is not None: svc.description = payload.description

    db.commit()
    return {"message": f"Service #{svc.id} updated successfully!"}


@router.delete("/services/{service_id}")
def delete_owner_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    svc = db.query(Service).filter(Service.id == service_id, Service.business_id == biz.id).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    svc.is_active = False
    db.commit()
    return {"message": f"Service #{service_id} removed successfully."}


# -------------------------------------------------------------------
# 5. STAFF / DOCTORS MANAGEMENT (CRUD)
# -------------------------------------------------------------------
@router.get("/staff")
def list_owner_staff(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    staff_list = db.query(Staff).filter(Staff.business_id == biz.id, Staff.is_active == True).all()
    return [
        {
            "id": st.id,
            "name": st.name,
            "role": st.role,
            "working_days": st.working_days,
            "working_start": st.working_start,
            "working_end": st.working_end,
            "break_start": st.break_start,
            "break_end": st.break_end,
            "supported_services": st.supported_services
        }
        for st in staff_list
    ]


@router.post("/staff")
def add_owner_staff(
    payload: StaffCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    stf = Staff(
        business_id=biz.id,
        name=payload.name,
        role=payload.role or "Specialist",
        working_days=payload.working_days or "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday",
        working_start=payload.working_start or "10:00",
        working_end=payload.working_end or "19:00",
        break_start=payload.break_start or "14:00",
        break_end=payload.break_end or "14:30",
        supported_services=payload.supported_services,
        is_active=True
    )
    db.add(stf)
    db.commit()
    db.refresh(stf)
    return {"message": f"Staff member '{stf.name}' added successfully!", "id": stf.id}


@router.put("/staff/{staff_id}")
def update_owner_staff(
    staff_id: int,
    payload: StaffCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    stf = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == biz.id).first()
    if not stf:
        raise HTTPException(status_code=404, detail="Staff member not found")

    if payload.name: stf.name = payload.name
    if payload.role: stf.role = payload.role
    if payload.working_days: stf.working_days = payload.working_days
    if payload.working_start: stf.working_start = payload.working_start
    if payload.working_end: stf.working_end = payload.working_end
    if payload.break_start: stf.break_start = payload.break_start
    if payload.break_end: stf.break_end = payload.break_end
    if payload.supported_services: stf.supported_services = payload.supported_services

    db.commit()
    return {"message": f"Staff member '{stf.name}' updated successfully!"}


@router.delete("/staff/{staff_id}")
def delete_owner_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    stf = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == biz.id).first()
    if not stf:
        raise HTTPException(status_code=404, detail="Staff member not found")

    stf.is_active = False
    db.commit()
    return {"message": f"Staff member #{staff_id} removed successfully."}


# -------------------------------------------------------------------
# 6. WORKING HOURS & BOOKING RULES MANAGEMENT
# -------------------------------------------------------------------
@router.get("/rules")
def get_owner_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    rules = db.query(BusinessRule).filter(BusinessRule.business_id == biz.id).all()
    rules_dict = {r.rule_key: r.rule_value for r in rules}
    return {
        "operating_hours": biz.operating_hours,
        "rules": rules_dict
    }


@router.put("/rules")
def update_owner_rules(
    payload: BookingRulesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    updates = {
        "min_notice_hours": str(payload.min_notice_hours),
        "max_advance_days": str(payload.max_advance_days),
        "cancellation_rules": payload.cancellation_rules,
        "rescheduling_rules": payload.rescheduling_rules,
        "booking_buffer_mins": str(payload.booking_buffer_mins),
        "max_group_size": str(payload.max_group_size),
        "deposit_requirements": payload.deposit_requirements,
        "late_arrival_rules": payload.late_arrival_rules
    }
    for r_key, r_val in updates.items():
        if r_val is not None:
            rule = db.query(BusinessRule).filter(BusinessRule.business_id == biz.id, BusinessRule.rule_key == r_key).first()
            if not rule:
                rule = BusinessRule(business_id=biz.id, rule_key=r_key, rule_value=str(r_val))
                db.add(rule)
            else:
                rule.rule_value = str(r_val)

    db.commit()
    return {"message": "Booking rules updated successfully!"}


@router.get("/business-hours")
def get_owner_business_hours(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    hours = ensure_default_business_hours(biz.id, db)
    day_order = {d: i for i, d in enumerate(DAYS_OF_WEEK)}
    sorted_hours = sorted(hours, key=lambda h: day_order.get(h.day, 99))
    return [
        {
            "id": h.id,
            "day": h.day,
            "opening_time": h.opening_time,
            "closing_time": h.closing_time,
            "is_open": h.is_open
        }
        for h in sorted_hours
    ]


@router.put("/business-hours")
def update_owner_business_hours(
    payload: MultiDayHoursUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    for item in payload.hours:
        h = db.query(BusinessHours).filter(
            BusinessHours.business_id == biz.id,
            BusinessHours.day == item.day
        ).first()
        if not h:
            h = BusinessHours(
                business_id=biz.id,
                day=item.day,
                opening_time=item.opening_time,
                closing_time=item.closing_time,
                is_open=item.is_open
            )
            db.add(h)
        else:
            h.opening_time = item.opening_time
            h.closing_time = item.closing_time
            h.is_open = item.is_open
    db.commit()
    return {"message": "Business operating hours updated successfully!"}


# -------------------------------------------------------------------
# 7. CUSTOMERS & APPOINTMENTS MANAGEMENT
# -------------------------------------------------------------------
@router.get("/customers")
def get_owner_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    appt_cust_ids = db.query(Appointment.customer_id).filter(Appointment.business_id == biz.id).distinct()

    customers = (
        db.query(Customer)
        .filter(or_(Customer.business_id == biz.id, Customer.id.in_(appt_cust_ids)))
        .order_by(Customer.created_at.desc())
        .all()
    )

    result = []
    for c in customers:
        appts = (
            db.query(Appointment)
            .filter(
                Appointment.business_id == biz.id,
                Appointment.customer_id == c.id
            )
            .order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.desc())
            .all()
        )
        last_appt_str = ""
        if appts:
            last_appt = appts[0]
            last_appt_str = f"{last_appt.appointment_date} ({last_appt.status})"
        elif c.created_at:
            last_appt_str = c.created_at.strftime("%Y-%m-%d")

        result.append({
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "email": c.email or "-",
            "total_bookings": len(appts),
            "last_visit": last_appt_str or "New",
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
        })
    return result


@router.get("/appointments")
def get_owner_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    appts = db.query(Appointment).filter(Appointment.business_id == biz.id).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.asc()).all()
    return [
        {
            "id": a.id,
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
            "notes": a.notes
        }
        for a in appts
    ]


@router.put("/appointments/{appointment_id}/status")
def update_appointment_status(
    appointment_id: int,
    status_val: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    appt = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.business_id == biz.id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appt.status = status_val
    db.commit()
    return {"message": f"Appointment #{appointment_id} status updated to '{status_val}'."}


# -------------------------------------------------------------------
# 8. OWNER AI BUSINESS CHATBOT
# -------------------------------------------------------------------
@router.post("/chat", response_model=OwnerChatResponse)
def owner_chat_endpoint(
    payload: OwnerChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner)
):
    biz = get_owner_business(current_user, db)
    agent = OwnerAgent(db=db, business_id=biz.id)
    res = agent.process(payload.message)
    return OwnerChatResponse(
        reply=res.get("reply", ""),
        action_taken=res.get("action_taken"),
        data=res.get("data")
    )
