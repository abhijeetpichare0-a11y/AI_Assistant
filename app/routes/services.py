from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceResponse

router = APIRouter(
    prefix="/services",
    tags=["Services"]
)

@router.post("/", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(data: ServiceCreate, db: Session = Depends(get_db)):
    service = Service(
        business_id=data.business_id,
        name=data.name,
        description=data.description,
        duration_minutes=data.duration_minutes,
        price=data.price,
        is_active=data.is_active
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service

@router.get("/", response_model=list[ServiceResponse])
def get_services(business_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Service)
    if business_id:
        query = query.filter(Service.business_id == business_id)
    return query.all()
