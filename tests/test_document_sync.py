import os
import sys
import unittest
from datetime import datetime
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.database import SessionLocal, engine, Base
from app.models import (
    User,
    Business,
    BusinessDocument,
    Service,
    BusinessHours,
    BusinessRule,
    BusinessFAQ,
)
from app.services.document_sync import sync_document_data_to_system
from app.agents.appointment_agent import AppointmentAgent
from app.agents.rag_agent import RAGAgent


class TestDocumentSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Business 1 (Target for Sync)
        cls.biz1 = cls.db.query(Business).filter(Business.name == "Zenith Wellness Spa").first()
        if not cls.biz1:
            cls.biz1 = Business(
                name="Zenith Wellness Spa",
                category="Salon & Spa",
                owner_name="Alice Owner",
                phone="9876543210",
                services_text="Basic Massage",
                description="Luxury wellness retreat",
                location="123 Serenity Way, Mumbai",
                currency="INR",
                timezone="Asia/Kolkata"
            )
            cls.db.add(cls.biz1)
            cls.db.commit()
            cls.db.refresh(cls.biz1)

        cls.owner1 = cls.db.query(User).filter(User.phone == "9876543210").first()
        if not cls.owner1:
            cls.owner1 = User(
                username="Alice Owner",
                phone="9876543210",
                role="owner",
                business_id=cls.biz1.id
            )
            cls.db.add(cls.owner1)
            cls.db.commit()
            cls.db.refresh(cls.owner1)

        # Business 2 (For Tenant Isolation Verification)
        cls.biz2 = cls.db.query(Business).filter(Business.name == "Echo Auto Garage").first()
        if not cls.biz2:
            cls.biz2 = Business(
                name="Echo Auto Garage",
                category="Auto Repair",
                owner_name="Bob Mechanic",
                phone="9876543299",
                services_text="Oil Change",
                description="Express repair shop",
                location="456 Motor Rd, Pune",
                currency="INR",
                timezone="Asia/Kolkata"
            )
            cls.db.add(cls.biz2)
            cls.db.commit()
            cls.db.refresh(cls.biz2)

        cls.owner2 = cls.db.query(User).filter(User.phone == "9876543299").first()
        if not cls.owner2:
            cls.owner2 = User(
                username="Bob Mechanic",
                phone="9876543299",
                role="owner",
                business_id=cls.biz2.id
            )
            cls.db.add(cls.owner2)
            cls.db.commit()
            cls.db.refresh(cls.owner2)

        cls.headers_owner1 = {
            "X-User-Phone": cls.owner1.phone,
            "X-User-Role": "owner"
        }
        cls.headers_owner2 = {
            "X-User-Phone": cls.owner2.phone,
            "X-User-Role": "owner"
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_sync_document_data_to_system_direct(self):
        """
        Direct test of sync_document_data_to_system extracting services, hours, rules, and FAQs.
        """
        doc_content = (
            "Zenith Wellness Spa Menu & Operating Guide\n\n"
            "Services & Rates:\n"
            "1. Swedish Full Body Massage: 60 mins - Rs. 2400 (Relaxing full body pressure therapy)\n"
            "2. Deep Tissue Therapy: 45 mins - Rs. 3000 (Targeted muscle tension relief)\n"
            "3. Organic Glow Facial: 30 mins - Rs. 1500 (Skin brightening herbal facial)\n\n"
            "Operating Hours:\n"
            "Monday to Friday: 09:00 AM - 08:00 PM\n"
            "Saturday: 10:00 AM - 07:00 PM\n"
            "Sunday: Closed\n\n"
            "Booking & Cancellation Policies:\n"
            "Cancellations must be made at least 24 hours prior to appointment for a full refund.\n"
            "A 20% advance deposit is required for packages exceeding Rs. 2000.\n"
            "Late arrivals beyond 15 minutes may result in reduced service duration.\n"
            "Maximum group size allowed is 6 guests per booking.\n\n"
            "Frequently Asked Questions:\n"
            "Q: Do you offer couple suites?\n"
            "A: Yes, couple massage suites are available with prior reservation.\n"
            "Q: Is parking available?\n"
            "A: Complimentary valet parking is provided for all spa guests.\n"
        )

        test_docs = [{
            "original_filename": "zenith_spa_menu.txt",
            "extracted_text": doc_content
        }]

        summary = sync_document_data_to_system(self.db, self.biz1.id, test_docs)

        self.assertGreater(summary["services_total"], 0)
        self.assertGreaterEqual(summary["hours_updated"], 1)
        self.assertGreaterEqual(summary["rules_updated"], 1)

        # Verify Services in DB
        swedish = self.db.query(Service).filter(
            Service.business_id == self.biz1.id,
            Service.name.ilike("%Swedish Full Body Massage%")
        ).first()
        self.assertIsNotNone(swedish)
        self.assertEqual(float(swedish.price), 2400.0)
        self.assertEqual(swedish.duration_minutes, 60)

        facial = self.db.query(Service).filter(
            Service.business_id == self.biz1.id,
            Service.name.ilike("%Organic Glow Facial%")
        ).first()
        self.assertIsNotNone(facial)
        self.assertEqual(float(facial.price), 1500.0)
        self.assertEqual(facial.duration_minutes, 30)

        # Verify BusinessHours in DB
        sunday_hours = self.db.query(BusinessHours).filter(
            BusinessHours.business_id == self.biz1.id,
            BusinessHours.day == "Sunday"
        ).first()
        if sunday_hours:
            self.assertFalse(sunday_hours.is_open)

        # Verify BusinessRule in DB
        cancel_rule = self.db.query(BusinessRule).filter(
            BusinessRule.business_id == self.biz1.id,
            BusinessRule.rule_key == "cancellation_rules"
        ).first()
        self.assertIsNotNone(cancel_rule)
        self.assertIn("24", cancel_rule.rule_value)

        # Verify BusinessFAQ in DB
        valet_faq = self.db.query(BusinessFAQ).filter(
            BusinessFAQ.business_id == self.biz1.id,
            BusinessFAQ.question.ilike("%parking%")
        ).first()
        self.assertIsNotNone(valet_faq)
        self.assertIn("valet", valet_faq.answer.lower())

    def test_02_upload_with_auto_sync_endpoint(self):
        """
        Verify POST /owner/documents with sync_to_system=True auto-syncs.
        """
        doc_text = (
            "Zenith Wellness Spa Supplementary Services\n"
            "1. Hot Stone Therapy: 50 mins - Rs. 3500\n"
            "2. Aromatherapy Bath: 40 mins - Rs. 2200\n"
        )
        files = [
            ("files", ("zenith_supplement.txt", doc_text.encode("utf-8"), "text/plain"))
        ]

        response = self.client.post(
            "/owner/documents",
            headers=self.headers_owner1,
            data={"sync_to_system": "true"},
            files=files
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("documents", data)
        self.assertIsNotNone(data.get("sync_summary"))

        # Verify new service created
        stone = self.db.query(Service).filter(
            Service.business_id == self.biz1.id,
            Service.name.ilike("%Hot Stone Therapy%")
        ).first()
        self.assertIsNotNone(stone)
        self.assertEqual(float(stone.price), 3500.0)

    def setUp(self):
        self.db.rollback()

    def test_03_sync_single_document_endpoint_and_isolation(self):
        """
        Verify POST /owner/documents/{doc_id}/sync updates system and enforces tenant isolation.
        """
        # Create a document for biz1
        doc1 = BusinessDocument(
            business_id=self.biz1.id,
            owner_id=self.owner1.id,
            original_filename="zenith_single_sync.txt",
            file_type="txt",
            file_path="uploads/zenith_single_sync.txt",
            file_size=120,
            extracted_text="Aromatherapy Foot Scrub: 25 mins - Rs. 950\nHours:\nMonday: 09:00 - 21:00\n",
            processing_status="processed",
            uploaded_at=datetime.utcnow()
        )
        self.db.add(doc1)
        self.db.commit()
        self.db.refresh(doc1)

        # Owner 2 attempts to sync Owner 1's document (Must return 403 Forbidden)
        res_unauthorized = self.client.post(
            f"/owner/documents/{doc1.id}/sync",
            headers=self.headers_owner2
        )
        self.assertEqual(res_unauthorized.status_code, 403)

        # Owner 1 syncs their own document (Must succeed 200 OK)
        res_authorized = self.client.post(
            f"/owner/documents/{doc1.id}/sync",
            headers=self.headers_owner1
        )
        self.assertEqual(res_authorized.status_code, 200)
        data = res_authorized.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("sync_summary", data)

        # Verify scrub was added
        scrub = self.db.query(Service).filter(
            Service.business_id == self.biz1.id,
            Service.name.ilike("%Aromatherapy Foot Scrub%")
        ).first()
        self.assertIsNotNone(scrub)
        self.assertEqual(float(scrub.price), 950.0)

    def test_04_sync_all_documents_endpoint(self):
        """
        Verify POST /owner/documents/sync-all endpoint syncs all owner docs.
        """
        response = self.client.post(
            "/owner/documents/sync-all",
            headers=self.headers_owner1
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("documents_count", data)
        self.assertIn("sync_summary", data)

    def test_05_appointment_agent_uses_synced_data(self):
        """
        Verify AppointmentAgent accurately responds with synced services and policies.
        """
        agent = AppointmentAgent(self.db)

        # Service list inquiry
        res_list = agent.process(
            message="What services do you provide?",
            customer_phone="9999988888",
            business_id=self.biz1.id
        )
        self.assertEqual(res_list["intent"], "SERVICE_LIST")
        self.assertIn("swedish full body massage", res_list["reply"].lower())

        # Pricing inquiry
        res_price = agent.process(
            message="How much is the Swedish Full Body Massage?",
            customer_phone="9999988888",
            business_id=self.biz1.id
        )
        self.assertIn("2400", res_price["reply"])

        # Cancellation policy inquiry
        res_policy = agent.process(
            message="What is your cancellation policy?",
            customer_phone="9999988888",
            business_id=self.biz1.id
        )
        self.assertEqual(res_policy["intent"], "CANCELLATION_POLICY")
        self.assertIn("cancellation policy", res_policy["reply"].lower())

    def test_06_rag_agent_uses_dynamic_business_answer_and_chunks(self):
        """
        Verify RAGAgent answers tenant queries using synced dynamic rules, services, and doc chunks,
        without falling back to generic event management text.
        """
        rag = RAGAgent()

        # 1. Services inquiry through RAG
        reply_services = rag.answer(
            question="What spa treatments and packages do you have?",
            db=self.db,
            business_id=self.biz1.id
        )
        self.assertIn("Zenith Wellness Spa", reply_services)
        self.assertIn("massage", reply_services.lower())
        self.assertNotIn("Event AI Assistant", reply_services)

        # 2. Operating hours through RAG
        reply_hours = rag.answer(
            question="What are your opening hours on Saturday?",
            db=self.db,
            business_id=self.biz1.id
        )
        self.assertIn("Saturday", reply_hours)
        self.assertNotIn("Event AI Assistant", reply_hours)

        # 3. Policy inquiry through RAG
        reply_policy = rag.answer(
            question="What is the cancellation policy?",
            db=self.db,
            business_id=self.biz1.id
        )
        self.assertIn("Cancellation Policy", reply_policy)
        self.assertIn("Zenith Wellness Spa", reply_policy)

        # 4. FAQ inquiry through RAG
        reply_faq = rag.answer(
            question="Is valet parking available?",
            db=self.db,
            business_id=self.biz1.id
        )
        self.assertIn("valet", reply_faq.lower())

        # 5. Document chunk retrieval (couple suites)
        reply_chunk = rag.answer(
            question="Do you have couple suites for massage?",
            db=self.db,
            business_id=self.biz1.id
        )
        self.assertIn("couple", reply_chunk.lower())

        # 6. Tenant isolation: Unrelated query should not mention generic Event AI Assistant
        reply_other = rag.answer(
            question="Can I bring my pet tiger?",
            db=self.db,
            business_id=self.biz1.id
        )
        self.assertIn("Zenith Wellness Spa", reply_other)
        self.assertNotIn("Event AI Assistant", reply_other)


if __name__ == "__main__":
    unittest.main()
