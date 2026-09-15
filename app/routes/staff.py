from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.staff import Staff
from app.schemas.staff import StaffCreate, StaffResponse

router = APIRouter(
    prefix="/staff",
    tags=["Staff"]
)

@router.post("/", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
def create_staff(data: StaffCreate, db: Session = Depends(get_db)):
    staff = Staff(
        business_id=data.business_id,
        name=data.name,
        role=data.role,
        is_active=data.is_active
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff

@router.get("/", response_model=list[StaffResponse])
def get_staff(business_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Staff)
    if business_id:
        query = query.filter(Staff.business_id == business_id)
    return query.all()
