import os
import sys
import unittest
from datetime import datetime, date, time
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.database import SessionLocal, engine, Base
from app.models import Business, Service, Customer, Appointment, BusinessHours

class TestPublicStorefrontAndProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Ensure a test business exists
        cls.biz = cls.db.query(Business).filter(Business.name == "Zenith Wellness Spa").first()
        if not cls.biz:
            cls.biz = Business(
                name="Zenith Wellness Spa",
                category="Salon & Spa",
                phone="9988776655",
                description="Luxury sanctuary offering holistic therapies.",
                location="742 Evergreen Terrace, Sector 4",
                currency="INR",
                timezone="Asia/Kolkata",
                operating_hours="09:00 AM - 08:00 PM"
            )
            cls.db.add(cls.biz)
            cls.db.commit()
            cls.db.refresh(cls.biz)

        # Ensure active service
        cls.svc = cls.db.query(Service).filter(Service.business_id == cls.biz.id).first()
        if not cls.svc:
            cls.svc = Service(
                business_id=cls.biz.id,
                name="Aromatherapy Massage",
                category="Massage",
                duration_minutes=60,
                price=1800.0,
                is_active=True
            )
            cls.db.add(cls.svc)
            cls.db.commit()
            cls.db.refresh(cls.svc)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_public_business_redirect(self):
        """Test /b/{business_id} redirects to /frontend/public_business.html?id={business_id}"""
        response = self.client.get(f"/b/{self.biz.id}", follow_redirects=False)
        self.assertIn(response.status_code, [302, 307])
        self.assertEqual(response.headers.get("location"), f"/frontend/public_business.html?id={self.biz.id}")

    def test_02_public_profile_endpoint_structure(self):
        """Test GET /businesses/{id}/public-profile returns valid, sanitized public information"""
        response = self.client.get(f"/businesses/{self.biz.id}/public-profile")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify Business object
        self.assertIn("business", data)
        biz_info = data["business"]
        self.assertEqual(biz_info["id"], self.biz.id)
        self.assertEqual(biz_info["name"], self.biz.name)
        self.assertIn("Spa", biz_info["category"])
        self.assertEqual(biz_info["currency"], "INR")

        # Verify Services list
        self.assertIn("services", data)
        self.assertTrue(len(data["services"]) >= 1)
        svc = data["services"][0]
        self.assertIn("name", svc)
        self.assertIn("price", svc)
        self.assertIn("duration_minutes", svc)

        # Verify 7-day Operating Hours
        self.assertIn("hours", data)
        self.assertEqual(len(data["hours"]), 7)
        days = [h["day"] for h in data["hours"]]
        self.assertIn("Monday", days)
        self.assertIn("Sunday", days)

        # Verify FAQs
        self.assertIn("faqs", data)

        # Strict Data Privacy Check: NO sensitive owner fields
        raw_text = response.text.lower()
        self.assertNotIn("password", raw_text)
        self.assertNotIn("hashed_password", raw_text)
        self.assertNotIn("secret", raw_text)

    def test_03_non_existent_business_public_profile(self):
        """Test GET /businesses/999999/public-profile returns 404"""
        response = self.client.get("/businesses/999999/public-profile")
        self.assertEqual(response.status_code, 404)

    def test_04_public_booking_flow(self):
        """Test customer booking flow and instant pass generation"""
        # Ensure customer exists or create one
        customer = self.db.query(Customer).filter(Customer.phone == "9199998888").first()
        if not customer:
            customer = Customer(
                business_id=self.biz.id,
                name="Public Tester",
                phone="9199998888",
                email="publictest@example.com"
            )
            self.db.add(customer)
            self.db.commit()
            self.db.refresh(customer)

        booking_payload = {
            "business_id": self.biz.id,
            "customer_id": customer.id,
            "service_id": self.svc.id,
            "event_type": self.svc.name,
            "appointment_date": "2026-11-20",
            "appointment_time": "14:30:00",
            "venue": "742 Evergreen Terrace",
            "guests": 1,
            "notes": "Booked from public storefront"
        }

        from app.models import Reminder
        old_appts = self.db.query(Appointment).filter(
            Appointment.appointment_date == date(2026, 11, 20),
            Appointment.appointment_time == time(14, 30)
        ).all()
        for a in old_appts:
            self.db.query(Reminder).filter(Reminder.appointment_id == a.id).delete()
            self.db.delete(a)
        self.db.commit()

        # Create appointment
        response = self.client.post("/appointments/", json=booking_payload)
        self.assertEqual(response.status_code, 201)
        appt_data = response.json()
        appt_id = appt_data["id"]
        self.assertTrue(appt_id > 0)

        # Verify PDF pass endpoint
        pdf_res = self.client.get(f"/appointments/{appt_id}/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers.get("content-type"), "application/pdf")
        self.assertTrue(len(pdf_res.content) > 1000)

if __name__ == "__main__":
    unittest.main()
