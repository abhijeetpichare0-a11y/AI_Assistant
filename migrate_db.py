from sqlalchemy import text
from app.database.database import engine, Base
import logging

logging.basicConfig(level=logging.INFO)

def run_migration():
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        logging.info("Checking and adding missing columns to PostgreSQL tables...")

        # 1. Businesses table columns
        biz_columns = [
            ("description", "TEXT"),
            ("currency", "VARCHAR(10) DEFAULT 'INR'"),
            ("timezone", "VARCHAR(50) DEFAULT 'Asia/Kolkata'"),
        ]
        for col_name, col_type in biz_columns:
            try:
                conn.execute(text(f"ALTER TABLE businesses ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
                logging.info(f"Added column {col_name} to businesses table.")
            except Exception as e:
                logging.warning(f"Notice adding {col_name} to businesses: {e}")

        # 2. Services table columns
        svc_columns = [
            ("category", "VARCHAR(100)"),
            ("deposit_percentage", "INTEGER DEFAULT 0"),
            ("required_resource_type", "VARCHAR(100)"),
        ]
        for col_name, col_type in svc_columns:
            try:
                conn.execute(text(f"ALTER TABLE services ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
                logging.info(f"Added column {col_name} to services table.")
            except Exception as e:
                logging.warning(f"Notice adding {col_name} to services: {e}")

        # 3. Staff table columns
        staff_columns = [
            ("working_days", "VARCHAR(200) DEFAULT 'Monday,Tuesday,Wednesday,Thursday,Friday,Saturday'"),
            ("working_start", "VARCHAR(10) DEFAULT '10:00'"),
            ("working_end", "VARCHAR(10) DEFAULT '19:00'"),
            ("break_start", "VARCHAR(10) DEFAULT '14:00'"),
            ("break_end", "VARCHAR(10) DEFAULT '14:30'"),
            ("supported_services", "TEXT"),
        ]
        for col_name, col_type in staff_columns:
            try:
                conn.execute(text(f"ALTER TABLE staff ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
                logging.info(f"Added column {col_name} to staff table.")
            except Exception as e:
                logging.warning(f"Notice adding {col_name} to staff: {e}")

    # Create new tables
    Base.metadata.create_all(bind=engine)
    logging.info("Migration completed successfully!")

if __name__ == "__main__":
    run_migration()
