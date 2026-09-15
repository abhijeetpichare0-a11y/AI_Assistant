from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from sqlalchemy import or_
from app.models import Customer, Appointment
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.services.validators import is_valid_name, is_valid_phone, is_valid_email


router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)


@router.post(
    "/",
    response_model=CustomerResponse,
    status_code=201
)
def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db)
):
    valid_name, err_name = is_valid_name(customer_data.name)
    if not valid_name:
        raise HTTPException(status_code=400, detail=f"Invalid Name: {err_name}")

    valid_phone, err_phone = is_valid_phone(customer_data.phone)
    if not valid_phone:
        raise HTTPException(status_code=400, detail=f"Invalid Phone: {err_phone}")

    if customer_data.email:
        valid_email, err_email = is_valid_email(customer_data.email)
        if not valid_email:
            raise HTTPException(status_code=400, detail=f"Invalid Email: {err_email}")

    existing_customer = (
        db.query(Customer)
        .filter(Customer.phone == customer_data.phone)
        .first()
    )

    if existing_customer:
        # Return existing customer, updating name/email if currently generic
        if customer_data.name and (not existing_customer.name or existing_customer.name == "Customer"):
            existing_customer.name = customer_data.name
        if customer_data.email and not existing_customer.email:
            existing_customer.email = customer_data.email
        db.commit()
        db.refresh(existing_customer)
        return existing_customer

    customer = Customer(
        business_id=customer_data.business_id,
        name=customer_data.name,
        phone=customer_data.phone,
        email=customer_data.email
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    return customer

@router.get(
    "/",
    response_model=list[CustomerResponse]
)
def get_customers(
    business_id: int | None = None,
    phone: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(Customer)
    if phone:
        query = query.filter(Customer.phone == phone)
    elif business_id:
        appt_sub = db.query(Appointment.customer_id).filter(Appointment.business_id == business_id).distinct()
        query = query.filter(or_(Customer.business_id == business_id, Customer.id.in_(appt_sub)))
    return query.order_by(Customer.id.desc()).all()
@router.get(
    "/{customer_id}",
    response_model=CustomerResponse
)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db)
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    return customer