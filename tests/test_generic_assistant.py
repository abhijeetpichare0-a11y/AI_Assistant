import sys
import os
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.database import SessionLocal
from app.agents.intent_detector import detect_intent
from app.agents.appointment_agent import AppointmentAgent
from app.agents.tools import (
    get_business_info,
    get_services,
    get_staff,
    calculate_price,
    calculate_deposit,
    check_availability
)
from app.models.service import Service
from app.models.staff import Staff

class TestGenericAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    # -------------------------------------------------------------
    # 1-5: Business Info & FAQs
    # -------------------------------------------------------------
    def test_01_business_info(self):
        intent = detect_intent("Tell me about GlowCare salon")
        self.assertEqual(intent, "BUSINESS_INFORMATION")

    def test_02_business_hours(self):
        intent = detect_intent("What are your opening hours on Saturday?")
        self.assertEqual(intent, "BUSINESS_HOURS")

    def test_03_business_location(self):
        intent = detect_intent("Where is your clinic located address?")
        self.assertEqual(intent, "BUSINESS_INFORMATION")

    def test_04_business_contact(self):
        intent = detect_intent("What is your phone number or contact details?")
        self.assertEqual(intent, "CONTACT_BUSINESS")

    def test_05_business_amenities(self):
        agent = AppointmentAgent(db=self.db)
        res = agent.process("Do you have parking and wifi?", business_id=1)
        self.assertIn("parking", res["reply"].lower())

    # -------------------------------------------------------------
    # 6-10: Service Listing & Pricing
    # -------------------------------------------------------------
    def test_06_service_listing(self):
        intent = detect_intent("What services do you offer?")
        self.assertEqual(intent, "SERVICE_LIST")

    def test_07_service_pricing(self):
        intent = detect_intent("How much does a Haircut cost?")
        self.assertEqual(intent, "SERVICE_PRICE")

    def test_08_service_duration(self):
        intent = detect_intent("How long does a Facial take?")
        self.assertEqual(intent, "SERVICE_DURATION")

    def test_09_service_category(self):
        services = get_services(self.db, business_id=1)
        hair_services = [s for s in services if s.category == "Hair"]
        self.assertTrue(len(hair_services) > 0)

    def test_10_service_details(self):
        intent = detect_intent("Tell me details about Hair Spa")
        self.assertEqual(intent, "SERVICE_DETAILS")

    # -------------------------------------------------------------
    # 11-15: Multi-Service & Bundling
    # -------------------------------------------------------------
    def test_11_multi_service_entity_extraction(self):
        agent = AppointmentAgent(db=self.db)
        agent.business_id = 1
        extracted = agent.extract_booking_details("I want haircut and hair spa")
        self.assertIn("Haircut", extracted["service_names"])
        self.assertIn("Hair Spa", extracted["service_names"])

    def test_12_multi_service_price_calculation(self):
        haircut = self.db.query(Service).filter(Service.business_id == 1, Service.name == "Haircut").first()
        hair_spa = self.db.query(Service).filter(Service.business_id == 1, Service.name == "Hair Spa").first()
        self.assertIsNotNone(haircut)
        self.assertIsNotNone(hair_spa)
        calc = calculate_price(self.db, 1, ["Haircut", "Hair Spa"])
        self.assertEqual(calc["total_price"], float(haircut.price + hair_spa.price))

    def test_13_multi_service_duration_calculation(self):
        haircut = self.db.query(Service).filter(Service.business_id == 1, Service.name == "Haircut").first()
        hair_spa = self.db.query(Service).filter(Service.business_id == 1, Service.name == "Hair Spa").first()
        calc = calculate_price(self.db, 1, ["Haircut", "Hair Spa"])
        self.assertEqual(calc["total_duration"], haircut.duration_minutes + hair_spa.duration_minutes)

    def test_14_deposit_calculation_multi_service(self):
        coloring = self.db.query(Service).filter(Service.business_id == 1, Service.name == "Hair Coloring").first()
        self.assertIsNotNone(coloring)
        dep = calculate_deposit(self.db, 1, ["Hair Coloring"])
        expected_dep = float(coloring.price) * (coloring.deposit_percentage / 100.0)
        self.assertAlmostEqual(dep["total_deposit"], expected_dep)

    def test_15_resource_requirement_check(self):
        facial = self.db.query(Service).filter(Service.business_id == 1, Service.name == "Facial").first()
        self.assertIsNotNone(facial.required_resource_type)

    # -------------------------------------------------------------
    # 16-20: Staff Capabilities & Schedules
    # -------------------------------------------------------------
    def test_16_staff_listing(self):
        staff_members = get_staff(self.db, business_id=1)
        self.assertGreaterEqual(len(staff_members), 3)

    def test_17_staff_capability(self):
        rahul = self.db.query(Staff).filter(Staff.business_id == 1, Staff.name == "Rahul").first()
        self.assertIn("Haircut", rahul.supported_services or "")

    def test_18_staff_working_days(self):
        rahul = self.db.query(Staff).filter(Staff.business_id == 1, Staff.name == "Rahul").first()
        self.assertIn("Monday", rahul.working_days)

    def test_19_staff_working_hours_and_breaks(self):
        rahul = self.db.query(Staff).filter(Staff.business_id == 1, Staff.name == "Rahul").first()
        self.assertEqual(str(rahul.working_start)[:5], "10:00")
        self.assertEqual(str(rahul.break_start)[:5], "14:00")

    def test_20_staff_incapability_rejection(self):
        rahul = self.db.query(Staff).filter(Staff.business_id == 1, Staff.name == "Rahul").first()
        self.assertNotIn("Dental Consultation", rahul.supported_services or "")

    # -------------------------------------------------------------
    # 21-25: Business Rules & Policies
    # -------------------------------------------------------------
    def test_21_cancellation_policy(self):
        intent = detect_intent("What is your cancellation policy?")
        self.assertEqual(intent, "CANCELLATION_POLICY")

    def test_22_deposit_policy(self):
        intent = detect_intent("Do I need to pay a deposit for booking?")
        self.assertEqual(intent, "DEPOSIT_INFORMATION")

    def test_23_reschedule_policy(self):
        intent = detect_intent("Can I reschedule my appointment?")
        self.assertEqual(intent, "RESCHEDULE_APPOINTMENT")

    def test_24_late_policy(self):
        intent = detect_intent("What if I arrive late for my appointment?")
        self.assertEqual(intent, "LATE_ARRIVAL")

    def test_25_refund_policy(self):
        intent = detect_intent("What is your refund policy?")
        self.assertEqual(intent, "CANCELLATION_POLICY")

    # -------------------------------------------------------------
    # 26-30: Multilingual Support (Hindi, Marathi, Hinglish)
    # -------------------------------------------------------------
    def test_26_hindi_greeting(self):
        intent = detect_intent("Namaste, mujhe appointment book karna hai")
        self.assertEqual(intent, "BOOK_APPOINTMENT")

    def test_27_hinglish_pricing(self):
        intent = detect_intent("Haircut price kitna hai?")
        self.assertEqual(intent, "SERVICE_PRICE")

    def test_28_marathi_greeting(self):
        intent = detect_intent("Namaskar, mala appointment book karaychi aahe")
        self.assertEqual(intent, "BOOK_APPOINTMENT")

    def test_29_hinglish_cancellation(self):
        intent = detect_intent("Mera appointment cancel kar do")
        self.assertEqual(intent, "CANCEL_APPOINTMENT")

    def test_30_hindi_timing_query(self):
        intent = detect_intent("Aaj kitne baje tak open hai?")
        self.assertEqual(intent, "BUSINESS_HOURS")

    # -------------------------------------------------------------
    # 31-35: Slot Search & Availability Logic
    # -------------------------------------------------------------
    def test_31_check_availability_valid_slot(self):
        res = check_availability(
            db=self.db,
            business_id=1,
            appointment_date="2026-09-10",
            appointment_time="11:00",
            service_names=["Haircut"],
            staff_name="Rahul"
        )
        self.assertTrue(res["available"])

    def test_32_check_availability_during_break(self):
        res = check_availability(
            db=self.db,
            business_id=1,
            appointment_date="2026-09-10",
            appointment_time="14:15",
            service_names=["Haircut"],
            staff_name="Rahul"
        )
        self.assertFalse(res["available"])
        self.assertIn("break", res["reason"].lower())

    def test_33_check_availability_outside_working_hours(self):
        res = check_availability(
            db=self.db,
            business_id=1,
            appointment_date="2026-09-10",
            appointment_time="07:00",
            service_names=["Haircut"],
            staff_name="Rahul"
        )
        self.assertFalse(res["available"])

    def test_34_check_availability_off_day(self):
        res = check_availability(
            db=self.db,
            business_id=1,
            appointment_date="2026-09-13", # Sunday
            appointment_time="10:00",
            service_names=["Haircut"]
        )
        self.assertFalse(res["available"])

    def test_35_buffer_time_enforcement(self):
        res = check_availability(
            db=self.db,
            business_id=1,
            appointment_date="2026-09-10",
            appointment_time="10:00",
            service_names=["Haircut", "Hair Spa"]
        )
        self.assertIn("total_duration", res)

    # -------------------------------------------------------------
    # 36-40: Chat Registration & State Preservation
    # -------------------------------------------------------------
    def test_36_agent_registration_prompt(self):
        agent = AppointmentAgent(db=self.db)
        res = agent.process("Book haircut tomorrow 10am", customer_phone="9998887776", business_id=1)
        self.assertTrue("name" in res["reply"].lower() or "book" in res["reply"].lower())

    def test_37_agent_step_by_step_booking(self):
        agent = AppointmentAgent(db=self.db)
        phone = "9876543210" # Existing user Aarav Sharma
        res1 = agent.process("I want to book a Haircut", customer_phone=phone, business_id=1)
        self.assertTrue(len(res1["reply"]) > 0)

    def test_38_phone_extraction(self):
        agent = AppointmentAgent(db=self.db)
        info = agent.extract_registration_info("My phone number is 9876543210")
        self.assertEqual(info.get("phone"), "9876543210")

    def test_39_email_extraction(self):
        agent = AppointmentAgent(db=self.db)
        info = agent.extract_registration_info("My email is aarav@example.com")
        self.assertEqual(info.get("email"), "aarav@example.com")

    def test_40_topic_switch_mid_flow(self):
        agent = AppointmentAgent(db=self.db)
        agent.process("Book haircut tomorrow 10am", customer_phone="9876543210", business_id=1)
        res2 = agent.process("Wait, what is your refund policy?", customer_phone="9876543210", business_id=1)
        self.assertTrue("cancellation" in res2["reply"].lower() or "refund" in res2["reply"].lower())

    # -------------------------------------------------------------
    # 41-45: Appointment Operations & Confirmation Notices
    # -------------------------------------------------------------
    def test_41_inquire_my_appointments(self):
        agent = AppointmentAgent(db=self.db)
        res = agent.process("Show my appointments", customer_phone="9876543210", business_id=1)
        self.assertTrue(len(res["reply"]) > 0)

    def test_42_reschedule_intent(self):
        intent = detect_intent("Reschedule my appointment to Friday at 3pm")
        self.assertEqual(intent, "RESCHEDULE_APPOINTMENT")

    def test_43_cancel_intent(self):
        intent = detect_intent("Cancel my booking for tomorrow")
        self.assertEqual(intent, "CANCEL_APPOINTMENT")

    def test_44_deposit_notice_in_confirmation(self):
        agent = AppointmentAgent(db=self.db)
        booking_data = {
            "event_type": "Hair Coloring",
            "service_names": ["Hair Coloring"],
            "appointment_date": "2026-09-10",
            "appointment_time": "10:00",
            "customer_name": "Aarav Sharma",
            "customer_phone": "9876543210",
            "customer_email": "aarav@example.com",
            "reg_name": "Aarav Sharma",
            "reg_phone": "9876543210",
            "reg_email": "aarav@example.com",
            "staff_name": "Priya",
            "staff_id": 2,
            "awaiting_field": "confirmation"
        }
        agent.pending_bookings["9876543210"] = booking_data
        agent.pending_bookings["1_9876543210"] = booking_data
        res = agent.process("Yes, confirm booking", customer_phone="9876543210", business_id=1)
        self.assertIn("deposit", res["reply"].lower())

    def test_45_reschedule_policy_inquiry(self):
        agent = AppointmentAgent(db=self.db)
        res = agent.process("Can I reschedule 2 hours before?", customer_phone="9876543210", business_id=1)
        self.assertTrue(len(res["reply"]) > 0)

    # -------------------------------------------------------------
    # 46-50: Multi-Business Isolation Tests (GlowCare vs Test Clinic)
    # -------------------------------------------------------------
    def test_46_glowcare_services_isolation(self):
        gc_services = get_services(self.db, business_id=1)
        tc_services = get_services(self.db, business_id=2)
        gc_names = [s.name for s in gc_services]
        tc_names = [s.name for s in tc_services]
        self.assertIn("Haircut", gc_names)
        self.assertNotIn("Dental Consultation", gc_names)
        self.assertIn("Dental Consultation", tc_names)

    def test_47_glowcare_staff_isolation(self):
        gc_staff = get_staff(self.db, business_id=1)
        tc_staff = get_staff(self.db, business_id=2)
        gc_staff_names = [s.name for s in gc_staff]
        tc_staff_names = [s.name for s in tc_staff]
        self.assertIn("Rahul", gc_staff_names)
        self.assertNotIn("Dr. Amit Sharma", gc_staff_names)
        self.assertIn("Dr. Amit Sharma", tc_staff_names)

    def test_48_test_clinic_hours_isolation(self):
        gc_info = get_business_info(self.db, business_id=1)
        tc_info = get_business_info(self.db, business_id=2)
        self.assertEqual(gc_info.name, "GlowCare Salon & Spa")
        self.assertIn(tc_info.name, ["Test Clinic", "HealthPlus Clinic"])

    def test_49_test_clinic_agent_response(self):
        agent_tc = AppointmentAgent(db=self.db)
        res = agent_tc.process("What services do you offer?", customer_phone="9123456789", business_id=2)
        self.assertIn("Dental", res["reply"])
        self.assertNotIn("Haircut", res["reply"])

    def test_50_multi_business_availability_isolation(self):
        res_tc = check_availability(
            db=self.db,
            business_id=2,
            appointment_date="2026-09-10",
            appointment_time="10:00",
            service_names=["Dental Consultation"],
            staff_name="Dr. Vikram Mehta"
        )
        self.assertTrue(res_tc["available"])

if __name__ == "__main__":
    unittest.main()
