from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional

from app.database.database import get_db
from app.models.user import User
from app.models.business import Business
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse, UserResponse

router = APIRouter(
    prefix="/auth",
    tags=["Authentication & Roles"]
)


def get_current_user(
    db: Session = Depends(get_db),
    x_user_phone: Optional[str] = Header(None, alias="X-User-Phone"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
) -> User:
    if not x_user_phone:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Phone header. Please log in first."
        )

    user = db.query(User).filter(User.phone == x_user_phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please log in."
        )

    if x_user_role and user.role != x_user_role and user.role != "superadmin":
        user.role = x_user_role
        db.commit()
        db.refresh(user)

    return user


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Superadmin master privileges required."
        )
    return current_user


def require_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["owner", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Owner role required."
        )
    return current_user


def require_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["user", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Customer/User role required."
        )
    return current_user


@router.post("/register", response_model=AuthResponse)
def register_endpoint(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    phone = payload.phone.strip()
    password = payload.password.strip()
    role = (payload.role or "owner").strip().lower()

    if role not in ["user", "owner", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'user', 'owner', or 'superadmin'"
        )

    if not username or not phone or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username, Mobile Number, and Password are all required for registration."
        )

    # Check if user already exists
    existing = db.query(User).filter(or_(User.phone == phone, User.username == username)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this Mobile Number or Username is already registered. Please click 'Sign In'."
        )

    business_id = None
    if role == "owner":
        biz = db.query(Business).filter(Business.phone == phone).first()
        if not biz:
            biz = db.query(Business).filter(Business.owner_name == username).first()
        if biz:
            business_id = biz.id

    new_user = User(
        username=username,
        phone=phone,
        password_hash=password,
        role=role,
        business_id=business_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    user_resp = UserResponse.from_orm(new_user)
    return AuthResponse(
        message=f"🎉 Registration successful! Welcome, {new_user.username} ({new_user.role.title()}).",
        user=user_resp
    )


@router.post("/login", response_model=AuthResponse)
def login_endpoint(payload: LoginRequest, db: Session = Depends(get_db)):
    login_id = payload.username.strip()
    password = payload.password.strip()

    if not login_id or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username/Mobile and Password are required."
        )

    # Find by username or phone
    user = db.query(User).filter(or_(User.username == login_id, User.phone == login_id)).first()

    # Fallback superadmin creation for Abhijeet or default admin IDs
    if not user and login_id in ["Abhijeet", "abhijeet", "9822713987", "admin", "superadmin", "9999999999"]:
        user = User(
            username="Abhijeet",
            phone="9822713987",
            password_hash="Abhi@2004",
            role="superadmin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found. Please click 'Register' to create a new account."
        )

    if user.password_hash and user.password_hash != password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again."
        )
    elif not user.password_hash:
        user.password_hash = password
        db.commit()
        db.refresh(user)

    user_resp = UserResponse.from_orm(user)
    return AuthResponse(
        message=f"Welcome back, {user.username}! Logged in as {user.role.title()}.",
        user=user_resp
    )


@router.get("/me", response_model=UserResponse)
def get_me_endpoint(current_user: User = Depends(get_current_user)):
    return current_user
