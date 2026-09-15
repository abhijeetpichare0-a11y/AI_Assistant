import logging
from app.database.database import SessionLocal, engine, Base
from app.services.business_config_loader import seed_all_businesses

logging.basicConfig(level=logging.INFO)

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        logging.info("Seeding all business configurations...")
        seed_all_businesses(db)
        logging.info("Database seeding completed successfully!")
    except Exception as e:
        logging.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
