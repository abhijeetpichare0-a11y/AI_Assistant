from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from app.routes.chatbot import router as chatbot_router
from app.database.database import Base, engine, get_db
from sqlalchemy.orm import Session
from app.models import Customer, Appointment, Reminder, Business
from app.routes.customers import router as customer_router
from app.routes.appointments import router as appointment_router
from app.routes.reminders import router as reminder_router
from app.routes.businesses import router as business_router
from app.routes.services import router as service_router
from app.routes.staff import router as staff_router
from app.routes.auth import router as auth_router
from app.routes.owner import router as owner_router
from app.routes.user import router as user_router
from app.routes.superadmin import router as superadmin_router
from app.routes.chatbot import router as chatbot_router
from app.scheduler.schedular import process_pending_reminders


# Create database tables
Base.metadata.create_all(bind=engine)


# Create scheduler
scheduler = BackgroundScheduler()


def reminder_job():
    try:
        processed = process_pending_reminders()

        if processed > 0:
            print(
                f"Reminder scheduler processed "
                f"{processed} reminder(s)"
            )

    except Exception as e:
        print(
            f"Reminder scheduler error: {e}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Start scheduler
    scheduler.add_job(
        reminder_job,
        "interval",
        minutes=1,
        id="reminder_job",
        replace_existing=True
    )

    scheduler.start()

    print("Reminder scheduler started")

    yield

    # Stop scheduler when application shuts down
    scheduler.shutdown()

    print("Reminder scheduler stopped")


app = FastAPI(
    title="Event Management AI Assistant",
    description="AI-powered appointment booking and reminder system",
    version="1.0.0",
    lifespan=lifespan
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routes
app.include_router(auth_router)
app.include_router(owner_router)
app.include_router(user_router)
app.include_router(superadmin_router)
app.include_router(customer_router)
app.include_router(appointment_router)
app.include_router(reminder_router)
app.include_router(business_router)
app.include_router(service_router)
app.include_router(staff_router)
app.include_router(chatbot_router)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pathlib import Path

# Static Files
BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

@app.get("/")
def root():
    return RedirectResponse(url="/frontend/index.html")

@app.get("/b/{business_id}")
def business_public_page_redirect(business_id: int):
    return RedirectResponse(url=f"/frontend/public_business.html?id={business_id}")


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }

@app.get("/availability")
def check_availability_endpoint(
    business_id: int = 1,
    date_str: str | None = None,
    time_str: str | None = None,
    staff_id: int | None = None,
    db: Session = Depends(get_db)
):
    from datetime import datetime
    from app.agents.tools import check_availability, get_services

    target_date = datetime.now().date()
    target_time = datetime.now().time()

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            pass

    if time_str:
        try:
            target_time = datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            try:
                target_time = datetime.strptime(time_str, "%I:%M %p").time()
            except ValueError:
                pass

    avail = check_availability(
        db=db,
        business_id=business_id,
        appointment_date=target_date,
        appointment_time=target_time,
        staff_id=staff_id
    )

    services = get_services(db, business_id)

    return {
        "business_id": business_id,
        "date": str(target_date),
        "time": str(target_time),
        "available": avail,
        "services_count": len(services)
    }