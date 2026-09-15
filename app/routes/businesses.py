from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.services.business_service import get_all_businesses, register_business
from app.models.business import Business
from app.models.service import Service
from app.models.staff import Staff
from app.models.resource import BusinessResource
from app.models.faq import BusinessFAQ
from app.models.business_hours import BusinessHours
from app.schemas.business import BusinessCreate, BusinessResponse

router = APIRouter(
    prefix="/businesses",
    tags=["Business Management & AI Training"]
)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_business_endpoint(data: BusinessCreate, db: Session = Depends(get_db)):
    try:
        business = register_business(
            db=db,
            name=data.name,
            category=data.category,
            services_text=data.services_text,
            phone=data.phone,
            location=data.location,
            owner_name=data.owner_name,
            operating_hours=data.operating_hours or "10:00 AM - 08:00 PM",
            timezone=data.timezone or "Asia/Kolkata"
        )
        return {
            "message": f"🎉 Business '{business.name}' registered successfully!",
            "business_id": business.id,
            "name": business.name
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/")
def list_businesses_endpoint(db: Session = Depends(get_db)):
    businesses = db.query(Business).all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "category": b.category,
            "location": b.location,
            "currency": b.currency,
            "phone": b.phone,
            "operating_hours": b.operating_hours
        }
        for b in businesses
    ]


@router.get("/{business_id}")
def get_business_by_id_endpoint(business_id: int, db: Session = Depends(get_db)):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    return {
        "id": biz.id,
        "name": biz.name,
        "category": biz.category,
        "location": biz.location,
        "currency": biz.currency,
        "timezone": biz.timezone,
        "phone": biz.phone,
        "operating_hours": biz.operating_hours,
        "description": biz.description
    }


@router.get("/{business_id}/services")
def get_business_services_endpoint(business_id: int, db: Session = Depends(get_db)):
    services = db.query(Service).filter(Service.business_id == business_id, Service.is_active == True).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "category": s.category,
            "duration_minutes": s.duration_minutes,
            "price": float(s.price or 0),
            "deposit_percentage": s.deposit_percentage,
            "description": s.description
        }
        for s in services
    ]


@router.get("/{business_id}/staff")
def get_business_staff_endpoint(business_id: int, db: Session = Depends(get_db)):
    staff_members = db.query(Staff).filter(Staff.business_id == business_id, Staff.is_active == True).all()
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
        for st in staff_members
    ]


@router.get("/{business_id}/resources")
def get_business_resources_endpoint(business_id: int, db: Session = Depends(get_db)):
    resources = db.query(BusinessResource).filter(BusinessResource.business_id == business_id, BusinessResource.is_active == True).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "resource_type": r.resource_type
        }
        for r in resources
    ]


@router.get("/{business_id}/faqs")
def get_business_faqs_endpoint(business_id: int, db: Session = Depends(get_db)):
    faqs = db.query(BusinessFAQ).filter(BusinessFAQ.business_id == business_id).all()
    return [
        {
            "id": f.id,
            "question": f.question,
            "answer": f.answer,
            "category": f.category
        }
        for f in faqs
    ]


@router.get("/{business_id}/hours")
def get_business_hours_endpoint(business_id: int, db: Session = Depends(get_db)):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    
    hours = db.query(BusinessHours).filter(BusinessHours.business_id == business_id).all()
    
    # Fallback to 7-day default if not yet populated
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours_dict = {h.day: h for h in hours}
    
    result = []
    for day in days_order:
        if day in hours_dict:
            h = hours_dict[day]
            result.append({
                "day": h.day,
                "is_open": h.is_open,
                "opening_time": h.opening_time or "10:00",
                "closing_time": h.closing_time or "20:00"
            })
        else:
            is_sun = (day == "Sunday")
            result.append({
                "day": day,
                "is_open": not is_sun,
                "opening_time": "10:00",
                "closing_time": "20:00"
            })
    return result


@router.get("/{business_id}/public-profile")
def get_business_public_profile_endpoint(business_id: int, db: Session = Depends(get_db)):
    """
    Returns public-facing profile for a business:
    - Business details (name, category, location, phone, description, currency)
    - Active services catalog (with price and duration)
    - 7-day operating hours
    - Public FAQs and policies
    Strictly excludes all owner credentials, owner revenues, and private settings.
    """
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
        
    services = db.query(Service).filter(
        Service.business_id == business_id,
        Service.is_active == True
    ).order_by(Service.category, Service.name).all()
    
    hours = db.query(BusinessHours).filter(BusinessHours.business_id == business_id).all()
    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    hours_dict = {h.day: h for h in hours}
    
    hours_list = []
    for day in days_order:
        if day in hours_dict:
            h = hours_dict[day]
            hours_list.append({
                "day": h.day,
                "is_open": h.is_open,
                "opening_time": h.opening_time or "10:00",
                "closing_time": h.closing_time or "20:00"
            })
        else:
            is_sun = (day == "Sunday")
            hours_list.append({
                "day": day,
                "is_open": not is_sun,
                "opening_time": "10:00",
                "closing_time": "20:00"
            })
            
    faqs = db.query(BusinessFAQ).filter(BusinessFAQ.business_id == business_id).all()

    return {
        "business": {
            "id": biz.id,
            "name": biz.name,
            "category": biz.category or "Services",
            "description": biz.description or f"Welcome to {biz.name}.",
            "location": biz.location or "Contact us for location details",
            "phone": biz.phone or "",
            "currency": biz.currency or "INR",
            "timezone": biz.timezone or "Asia/Kolkata",
            "operating_hours_summary": biz.operating_hours or "10:00 AM - 08:00 PM"
        },
        "services": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category or "General",
                "duration_minutes": s.duration_minutes,
                "price": float(s.price or 0),
                "deposit_percentage": s.deposit_percentage,
                "description": s.description or ""
            }
            for s in services
        ],
        "hours": hours_list,
        "faqs": [
            {
                "id": f.id,
                "question": f.question,
                "answer": f.answer,
                "category": f.category
            }
            for f in faqs
        ]
    }

