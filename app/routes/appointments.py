from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.reminder_service import create_appointment_reminders
from app.database.database import get_db
from app.models import Appointment, Customer
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
)


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"]
)


@router.post(
    "/",
    response_model=AppointmentResponse,
    status_code=201
)
def create_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db)
):
    # Check customer
    customer = (
        db.query(Customer)
        .filter(Customer.id == appointment_data.customer_id)
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    # Check whether slot is already booked for this business
    existing_appointment_query = (
        db.query(Appointment)
        .filter(
            Appointment.business_id == appointment_data.business_id,
            Appointment.appointment_date == appointment_data.appointment_date,
            Appointment.appointment_time == appointment_data.appointment_time,
            Appointment.status == "confirmed"
        )
    )
    if appointment_data.staff_id:
        existing_appointment_query = existing_appointment_query.filter(
            Appointment.staff_id == appointment_data.staff_id
        )

    if existing_appointment_query.first():
        raise HTTPException(
            status_code=409,
            detail="This appointment slot is already booked for this business/specialist"
        )

    # Create appointment
    appointment = Appointment(
        business_id=appointment_data.business_id,
        customer_id=appointment_data.customer_id,
        service_id=appointment_data.service_id,
        staff_id=appointment_data.staff_id,
        event_type=appointment_data.event_type,
        appointment_date=appointment_data.appointment_date,
        appointment_time=appointment_data.appointment_time,
        venue=appointment_data.venue,
        guests=appointment_data.guests,
        notes=appointment_data.notes,
        status="confirmed"
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    create_appointment_reminders(
        appointment,
        db
    )

    # Generate PDF Confirmation Pass
    from app.services.pdf_service import generate_appointment_pdf
    from app.services.whatsapp_provider import RSLWhatsAppProvider

    pdf_filepath, pdf_url = generate_appointment_pdf(db, appointment)

    # Dispatch Instant WhatsApp Confirmation with PDF document
    try:
        confirm_msg = (
            f"🎉 APPOINTMENT CONFIRMED!\n\n"
            f"Dear {customer.name},\n"
            f"Your booking for '{appointment.event_type}' has been successfully confirmed!\n\n"
            f"🆔 Booking ID: #{appointment.id}\n"
            f"📅 Date: {appointment.appointment_date}\n"
            f"⏰ Time: {appointment.appointment_time}\n"
            f"📍 Venue: {appointment.venue or 'Main Venue'}\n"
            f"👥 Guests: {appointment.guests or 1}\n\n"
            f"📄 Your Official Appointment PDF Pass has been attached directly to this message.\n\n"
            f"Automated reminders and updates will be sent prior to your appointment."
        )
        RSLWhatsAppProvider().send(customer, appointment, confirm_msg, pdf_url=pdf_url, pdf_filepath=pdf_filepath)
    except Exception as e:
        print(f"[Instant WhatsApp Confirmation Notice]: {e}")

    return appointment


from fastapi.responses import FileResponse

@router.get("/{appointment_id}/pdf")
def get_appointment_pdf(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    from app.services.pdf_service import generate_appointment_pdf
    filepath, _ = generate_appointment_pdf(db, appointment)
    return FileResponse(filepath, media_type="application/pdf", filename=f"appointment_pass_{appointment_id}.pdf")

@router.get(
    "/",
    response_model=list[AppointmentResponse]
)
def get_appointments(
    business_id: int | None = None,
    customer_phone: str | None = None,
    include_cancelled: bool = True,
    db: Session = Depends(get_db)
):
    query = db.query(Appointment)
    if business_id:
        query = query.filter(Appointment.business_id == business_id)
    if customer_phone:
        clean = customer_phone.strip()
        cust_ids = [c[0] for c in db.query(Customer.id).filter(Customer.phone.contains(clean)).all()]
        if cust_ids:
            query = query.filter(Appointment.customer_id.in_(cust_ids))
        else:
            return []
    if not include_cancelled:
        query = query.filter(Appointment.status != "cancelled")
        
    appointments = (
        query
        .order_by(
            Appointment.appointment_date.desc(),
            Appointment.appointment_time.desc()
        )
        .all()
    )

    return appointments

@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse
)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    return appointment


@router.put(
    "/{appointment_id}",
    response_model=AppointmentResponse
)
def update_appointment(
    appointment_id: int,
    appointment_data: AppointmentUpdate,
    db: Session = Depends(get_db)
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    if appointment_data.event_type is not None:
        appointment.event_type = (
            appointment_data.event_type
        )

    if appointment_data.appointment_date is not None:
        appointment.appointment_date = (
            appointment_data.appointment_date
        )

    if appointment_data.appointment_time is not None:
        appointment.appointment_time = (
            appointment_data.appointment_time
        )

    if appointment_data.venue is not None:
        appointment.venue = appointment_data.venue

    if appointment_data.guests is not None:
        appointment.guests = appointment_data.guests

    if appointment_data.notes is not None:
        appointment.notes = appointment_data.notes

    db.commit()
    db.refresh(appointment)

    return appointment


@router.post("/{appointment_id}/cancel")
@router.delete("/{appointment_id}")
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db)
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found"
        )

    appointment.status = "cancelled"
    db.commit()

    # Dispatch Instant WhatsApp Cancellation Notice
    try:
        from app.services.whatsapp_provider import RSLWhatsAppProvider
        customer = db.query(Customer).filter(Customer.id == appointment.customer_id).first()
        if customer:
            cancel_msg = (
                f"❌ APPOINTMENT CANCELLED\n\n"
                f"Dear {customer.name},\n"
                f"Your appointment #{appointment.id} for '{appointment.event_type}' on {appointment.appointment_date} at {appointment.appointment_time} has been cancelled.\n\n"
                f"Feel free to visit our booking portal anytime if you would like to schedule a new appointment."
            )
            RSLWhatsAppProvider().send(customer, appointment, cancel_msg)
    except Exception as e:
        print(f"[Cancellation WhatsApp Notice]: {e}")

    return {
        "message": "Appointment cancelled successfully",
        "appointment_id": appointment.id
    }