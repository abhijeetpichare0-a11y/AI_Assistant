from datetime import date, time, datetime, timedelta
from sqlalchemy.orm import Session
from app.models import Appointment, Customer, Business, Service, Staff, BusinessResource, BusinessRule, BusinessFAQ


# =========================================================
# BUSINESS INFORMATION TOOLS
# =========================================================

def get_business_info(db: Session, business_id: int):
    return db.query(Business).filter(Business.id == business_id).first()


def get_services(db: Session, business_id: int):
    return db.query(Service).filter(Service.business_id == business_id, Service.is_active == True).all()


def get_service_details(db: Session, business_id: int, service_name: str):
    exact = (
        db.query(Service)
        .filter(
            Service.business_id == business_id,
            Service.name.ilike(service_name),
            Service.is_active == True
        )
        .first()
    )
    if exact:
        return exact

    return (
        db.query(Service)
        .filter(
            Service.business_id == business_id,
            Service.name.ilike(f"%{service_name}%"),
            Service.is_active == True
        )
        .first()
    )


def get_staff(db: Session, business_id: int):
    return db.query(Staff).filter(Staff.business_id == business_id, Staff.is_active == True).all()


def get_staff_services(db: Session, business_id: int, staff_identifier: str | int):
    query = db.query(Staff).filter(Staff.business_id == business_id, Staff.is_active == True)
    if isinstance(staff_identifier, int):
        staff = query.filter(Staff.id == staff_identifier).first()
    else:
        staff = query.filter(Staff.name.ilike(f"%{staff_identifier}%")).first()

    if not staff or not staff.supported_services:
        return []

    services_list = [s.strip() for s in staff.supported_services.split(",") if s.strip()]
    return services_list


def calculate_price(db: Session, business_id: int, service_identifiers: list[str | int]) -> dict:
    total_price = 0.0
    total_duration = 0
    services_found = []

    for item in service_identifiers:
        if isinstance(item, int):
            svc = db.query(Service).filter(Service.id == item, Service.business_id == business_id).first()
        else:
            svc = get_service_details(db, business_id, item)

        if svc:
            total_price += float(svc.price or 0)
            total_duration += svc.duration_minutes or 30
            services_found.append(svc)

    return {
        "total_price": total_price,
        "total_duration": total_duration,
        "services": services_found
    }


def calculate_deposit(db: Session, business_id: int, service_identifiers: list[str | int]) -> dict:
    price_info = calculate_price(db, business_id, service_identifiers)
    deposit_amount = 0.0
    required_services = []

    for svc in price_info["services"]:
        if (svc.deposit_percentage or 0) > 0:
            dep = float(svc.price or 0) * (svc.deposit_percentage / 100.0)
            deposit_amount += dep
            required_services.append((svc.name, svc.deposit_percentage, dep))

    return {
        "total_deposit": deposit_amount,
        "deposit_required": deposit_amount > 0,
        "details": required_services
    }


def get_resources(db: Session, business_id: int):
    return db.query(BusinessResource).filter(BusinessResource.business_id == business_id, BusinessResource.is_active == True).all()


def get_business_rules(db: Session, business_id: int) -> dict:
    rules = db.query(BusinessRule).filter(BusinessRule.business_id == business_id).all()
    return {r.rule_key: r.rule_value for r in rules}


def get_business_faqs(db: Session, business_id: int, query: str | None = None):
    q = db.query(BusinessFAQ).filter(BusinessFAQ.business_id == business_id)
    if query:
        q = q.filter(
            (BusinessFAQ.question.ilike(f"%{query}%")) |
            (BusinessFAQ.answer.ilike(f"%{query}%"))
        )
    return q.all()


# =========================================================
# CHECK AVAILABILITY
# =========================================================

def check_availability(
    db: Session,
    business_id: int,
    appointment_date: date | str,
    appointment_time: time | str,
    staff_id: int | None = None,
    staff_name: str | None = None,
    service_names: list[str] | None = None,
    party_size: int = 1,
    exclude_appointment_id: int | None = None
) -> dict:
    """
    Business-aware availability checker evaluating:
    - Business hours
    - Staff working days, shift hours & breaks
    - Staff service capabilities
    - Resource conflicts
    - Buffer time (10 mins)
    - Overlapping existing appointments
    """
    if isinstance(appointment_date, str):
        try:
            appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
        except ValueError:
            return {"available": False, "reason": "Invalid date format"}

    if isinstance(appointment_time, str):
        try:
            appointment_time = datetime.strptime(appointment_time, "%H:%M").time()
        except ValueError:
            return {"available": False, "reason": "Invalid time format"}

    business = get_business_info(db, business_id)
    if not business:
        return {"available": False, "reason": "Business not found"}

    # Resolve staff_name if staff_id is None
    if staff_id is None and staff_name:
        stf_obj = db.query(Staff).filter(
            Staff.business_id == business_id,
            Staff.name.ilike(f"%{staff_name}%")
        ).first()
        if stf_obj:
            staff_id = stf_obj.id

    # 1. Day of week check
    day_name = appointment_date.strftime("%A")

    # 2. Staff capability & shift check if staff specified
    if staff_id:
        stf = db.query(Staff).filter(Staff.id == staff_id, Staff.business_id == business_id).first()
        if not stf or not stf.is_active:
            return {"available": False, "reason": "Staff member not active or not found"}

        if stf.working_days and day_name not in stf.working_days:
            return {"available": False, "reason": f"{stf.name} does not work on {day_name}s"}

        # Parse shift and break times
        try:
            start_t = datetime.strptime(str(stf.working_start or "10:00")[:5], "%H:%M").time()
            end_t = datetime.strptime(str(stf.working_end or "19:00")[:5], "%H:%M").time()
            b_start = datetime.strptime(str(stf.break_start or "14:00")[:5], "%H:%M").time()
            b_end = datetime.strptime(str(stf.break_end or "14:30")[:5], "%H:%M").time()

            if appointment_time < start_t or appointment_time >= end_t:
                return {"available": False, "reason": f"Requested time is outside working hours ({start_t.strftime('%H:%M')} - {end_t.strftime('%H:%M')})"}
            if b_start <= appointment_time < b_end:
                return {"available": False, "reason": f"Staff is on break ({b_start.strftime('%H:%M')} - {b_end.strftime('%H:%M')})"}
        except ValueError:
            pass

        # Service capabilities check
        if service_names and stf.supported_services:
            supported = [s.strip().lower() for s in stf.supported_services.split(",")]
            for req_service in service_names:
                if not any(req_service.lower() in sup for sup in supported):
                    return {"available": False, "reason": f"Staff does not perform service: {req_service}"}

    # 3. Dynamic business open days & hours check
    from app.models.business_hours import BusinessHours
    biz_day_hours = db.query(BusinessHours).filter(
        BusinessHours.business_id == business_id,
        BusinessHours.day == day_name
    ).first()
    if biz_day_hours:
        if not biz_day_hours.is_open:
            return {"available": False, "reason": f"{business.name} is closed on {day_name}s"}
        if biz_day_hours.opening_time and biz_day_hours.closing_time:
            try:
                open_t = datetime.strptime(str(biz_day_hours.opening_time)[:5], "%H:%M").time()
                close_t = datetime.strptime(str(biz_day_hours.closing_time)[:5], "%H:%M").time()
                if appointment_time < open_t or appointment_time >= close_t:
                    return {
                        "available": False,
                        "reason": f"Requested time is outside business hours ({biz_day_hours.opening_time} - {biz_day_hours.closing_time})"
                    }
            except ValueError:
                pass
    elif day_name in ["Sunday"]:
        return {"available": False, "reason": "Business is closed on Sundays"}

    # 4. Calculate total duration for requested services
    duration_minutes = 30
    if service_names:
        price_info = calculate_price(db, business_id, service_names)
        if price_info["total_duration"] > 0:
            duration_minutes = price_info["total_duration"]

    buffer_mins = 10
    total_slot_minutes = duration_minutes + buffer_mins

    # 5. Check staff & resource conflicts against existing DB appointments
    app_dt_start = datetime.combine(appointment_date, appointment_time)
    app_dt_end = app_dt_start + timedelta(minutes=total_slot_minutes)

    existing_query = db.query(Appointment).filter(
        Appointment.business_id == business_id,
        Appointment.appointment_date == appointment_date,
        Appointment.status == "confirmed"
    )
    if exclude_appointment_id:
        existing_query = existing_query.filter(Appointment.id != exclude_appointment_id)

    existing_appointments = existing_query.all()

    for ex in existing_appointments:
        ex_start = datetime.combine(ex.appointment_date, ex.appointment_time)
        ex_duration = 30
        if ex.service_id:
            svc = db.query(Service).get(ex.service_id)
            if svc:
                ex_duration = svc.duration_minutes
        ex_end = ex_start + timedelta(minutes=ex_duration + buffer_mins)

        if max(app_dt_start, ex_start) < min(app_dt_end, ex_end):
            if staff_id and ex.staff_id == staff_id:
                return {"available": False, "reason": "Staff member already has a booking at this time"}

    return {
        "available": True,
        "reason": "Slot is available",
        "total_duration": duration_minutes,
        "buffer_minutes": buffer_mins
    }


# =========================================================
# CUSTOMER & APPOINTMENT OPERATIONS
# =========================================================

def find_customer(db: Session, business_id: int, phone: str):
    exact = (
        db.query(Customer)
        .filter(Customer.phone == phone, Customer.business_id == business_id)
        .first()
    )
    if exact:
        return exact
    return db.query(Customer).filter(Customer.phone == phone).first()


def create_customer(db: Session, business_id: int, name: str, phone: str, email: str | None = None):
    existing = db.query(Customer).filter(Customer.phone == phone).first()
    if existing:
        existing.name = name or existing.name
        existing.email = email or existing.email
        db.commit()
        db.refresh(existing)
        return existing

    customer = Customer(
        business_id=business_id,
        name=name,
        phone=phone,
        email=email
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def book_appointment(
    db: Session,
    business_id: int,
    customer_id: int,
    event_type: str,
    appointment_date: date,
    appointment_time: time,
    venue: str | None = None,
    guests: int | None = 1,
    notes: str | None = None,
    service_id: int | None = None,
    staff_id: int | None = None
):
    appointment = Appointment(
        business_id=business_id,
        customer_id=customer_id,
        service_id=service_id,
        staff_id=staff_id,
        event_type=event_type,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        venue=venue,
        guests=guests or 1,
        notes=notes,
        status="confirmed"
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def get_customer_appointments(db: Session, customer_id: int, include_cancelled: bool = False):
    query = db.query(Appointment).filter(Appointment.customer_id == customer_id)
    if not include_cancelled:
        query = query.filter(Appointment.status != "cancelled")
    return query.order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc()).all()


def get_appointment_by_id(db: Session, appointment_id: int, customer_id: int | None = None):
    query = db.query(Appointment).filter(Appointment.id == appointment_id)
    if customer_id is not None:
        query = query.filter(Appointment.customer_id == customer_id)
    return query.first()


def cancel_appointment(db: Session, appointment: Appointment):
    if appointment.status == "cancelled":
        return appointment

    appointment.status = "cancelled"
    db.commit()
    db.refresh(appointment)
    return appointment
