import os
import sys
import unittest
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.database import SessionLocal, engine, Base
from app.models import (
    Business,
    Service,
    BusinessHours,
    BusinessDocument,
    BusinessFAQ,
    BusinessRule
)
from app.services.document_parser import (
    extract_text_from_txt,
    extract_text_from_csv,
    parse_and_save_uploaded_file
)
from app.services.ai_business_extractor import extract_business_profile_from_documents
from app.agents.tools import check_availability
from app.agents.rag_agent import RAGAgent

class TestDocumentOnboarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        
        # Ensure a clean test business
        cls.test_biz = cls.db.query(Business).filter(Business.name == "Zenith Wellness Spa").first()
        if not cls.test_biz:
            cls.test_biz = Business(
                name="Zenith Wellness Spa",
                category="Wellness & Spa",
                phone="+91-9988776655",
                services_text="Swedish Massage, Deep Tissue",
                description="Holistic health and wellness sanctuary.",
                location="742 Evergreen Terrace, Sector 4",
                currency="INR",
                timezone="Asia/Kolkata"
            )
            cls.db.add(cls.test_biz)
            cls.db.commit()
            cls.db.refresh(cls.test_biz)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_document_parser_text(self):
        sample_text = "Zenith Wellness Spa offers Swedish Massage for INR 1500 and Deep Tissue for INR 2200."
        parsed = extract_text_from_txt(sample_text.encode("utf-8"))
        self.assertIn("Swedish Massage", parsed)
        self.assertIn("1500", parsed)

    def test_02_document_parser_csv(self):
        sample_csv = "Service,Price,Duration\nAromatherapy,1800,60\nHot Stone Therapy,2500,90\n"
        parsed = extract_text_from_csv(sample_csv.encode("utf-8"))
        self.assertIn("Aromatherapy", parsed)
        self.assertIn("1800", parsed)

    def test_03_ai_business_extractor_heuristic(self):
        docs = [
            {
                "original_filename": "spa_brochure.txt",
                "extracted_text": (
                    "Welcome to Zenith Wellness Spa!\n"
                    "Address: 742 Evergreen Terrace.\n"
                    "Contact us at +91-9988776655.\n"
                    "Swedish Massage | ₹1500 | 60 mins\n"
                    "Deep Tissue Massage | ₹2200 | 60 mins\n"
                    "Operating hours: Mon-Fri 09:00 - 20:00, Saturday 10:00 - 18:00. Sunday: Closed.\n"
                    "Policy: Free cancellation up to 2 hours before appointment.\n"
                    "Q: Do you offer couples massage? A: Yes, couple packages are available."
                )
            }
        ]
        extracted = extract_business_profile_from_documents(docs)
        self.assertEqual(extracted.business_name, "Zenith Wellness Spa")
        self.assertEqual(extracted.category, "Salon & Spa")
        self.assertTrue(len(extracted.services) >= 2)
        
        # Check operating hours
        hours_map = {h.day: h for h in extracted.business_hours}
        self.assertEqual(len(hours_map), 7)
        self.assertFalse(hours_map["Sunday"].is_open)
        self.assertTrue(hours_map["Monday"].is_open)

    def test_04_multi_document_conflict_detection(self):
        docs = [
            {
                "original_filename": "menu_2025.txt",
                "extracted_text": "Swedish Massage | ₹1500 | 60 mins"
            },
            {
                "original_filename": "summer_flyer.txt",
                "extracted_text": "Swedish Massage | ₹1200 | 60 mins"
            }
        ]
        extracted = extract_business_profile_from_documents(docs)
        conflicts = extracted.conflicts
        self.assertTrue(len(conflicts) >= 1)
        conflict = conflicts[0]
        self.assertIn("swedish massage", conflict.item_name.lower())
        self.assertIn("1500", conflict.value1)
        self.assertIn("1200", conflict.value2)

    def test_05_database_business_hours_and_availability(self):
        biz_id = self.test_biz.id
        # Remove any existing hours
        self.db.query(BusinessHours).filter(BusinessHours.business_id == biz_id).delete()
        
        # Configure Wednesday as Closed and Tuesday as Open (09:00 to 18:00)
        days = [
            ("Monday", "09:00", "18:00", True),
            ("Tuesday", "09:00", "18:00", True),
            ("Wednesday", "09:00", "18:00", False), # Wednesday Closed!
            ("Thursday", "09:00", "18:00", True),
            ("Friday", "09:00", "18:00", True),
            ("Saturday", "10:00", "16:00", True),
            ("Sunday", "00:00", "00:00", False)
        ]
        for day, op, cl, is_op in days:
            self.db.add(BusinessHours(
                business_id=biz_id,
                day=day,
                opening_time=op,
                closing_time=cl,
                is_open=is_op
            ))
        self.db.commit()

        # Add a test service
        svc = self.db.query(Service).filter(Service.business_id == biz_id, Service.name == "Zenith Massage").first()
        if not svc:
            svc = Service(business_id=biz_id, name="Zenith Massage", duration_minutes=60, price=1500.0)
            self.db.add(svc)
            self.db.commit()

        # Check availability on a Tuesday (2026-09-15 is a Tuesday)
        avail_tuesday = check_availability(
            db=self.db,
            business_id=biz_id,
            appointment_date="2026-09-15",
            appointment_time="11:00",
            service_names=["Zenith Massage"]
        )
        self.assertTrue(avail_tuesday["available"], f"Tuesday should be open: {avail_tuesday}")

        # Check availability on a Wednesday (2026-09-16 is a Wednesday, which we marked as Closed)
        avail_wednesday = check_availability(
            db=self.db,
            business_id=biz_id,
            appointment_date="2026-09-16",
            appointment_time="11:00",
            service_names=["Zenith Massage"]
        )
        self.assertFalse(avail_wednesday["available"], "Wednesday should be closed")
        self.assertIn("closed", avail_wednesday["reason"].lower())

    def test_06_rag_agent_live_hours_and_faqs(self):
        biz_id = self.test_biz.id
        # Add a business FAQ
        self.db.query(BusinessFAQ).filter(BusinessFAQ.business_id == biz_id).delete()
        faq = BusinessFAQ(
            business_id=biz_id,
            question="Do you have organic herbal oils?",
            answer="Yes, all treatments use 100% certified organic Himalayan herbal oils."
        )
        self.db.add(faq)
        self.db.commit()

        rag = RAGAgent()
        
        # Test asking about hours
        ans_hours = rag.answer(
            question="What are your hours on Wednesday?",
            db=self.db,
            business_id=biz_id
        )
        self.assertIn("wednesday", ans_hours.lower())
        self.assertIn("closed", ans_hours.lower())

        # Test asking about FAQ
        ans_faq = rag.answer(
            question="Do you have organic herbal oils?",
            db=self.db,
            business_id=biz_id
        )
        self.assertIn("organic", ans_faq.lower())

if __name__ == "__main__":
    unittest.main()
