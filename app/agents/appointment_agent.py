import re
from datetime import date, datetime, timedelta, time
from sqlalchemy.orm import Session

from app.models import Appointment, Customer, Business, Service, Staff, BusinessResource, BusinessRule, BusinessFAQ
from app.agents.intent_detector import detect_intent
from app.agents.tools import (
    book_appointment,
    cancel_appointment,
    check_availability,
    create_customer,
    find_customer,
    get_appointment_by_id,
    get_customer_appointments,
    get_business_info,
    get_services,
    get_service_details,
    get_staff,
    get_staff_services,
    calculate_price,
    calculate_deposit,
    get_resources,
    get_business_rules,
    get_business_faqs,
)
from app.services.reminder_service import create_appointment_reminders
from app.services.validators import is_valid_name, is_valid_phone, is_valid_email


class AppointmentAgent:
    """
    Generic Multi-Business AI Booking Agent

    Features:
    - Multi-tenant business isolation (business_id)
    - Dynamic service & staff catalog matching
    - Multi-service bookings (combined duration & price calculation)
    - Staff schedules, working days, shifts, breaks & service permissions
    - Resource conflict checking (e.g. Coloring Station, Facial Room, Spa Room, Nail Station)
    - Deposit requirement checks & calculation
    - Topic switching & State Override (answers pricing/policy mid-booking cleanly)
    - Multilingual intent & entity extraction (English, Hindi, Marathi, Hinglish)
    """

    pending_bookings = {}

    AVAILABLE_HOURS = range(10, 21)
    DATE_LOOKAHEAD_DAYS = 30
    MAX_SUGGESTED_DATES = 8
    MAX_SUGGESTED_TIMES = 8

    def __init__(self, db: Session):
        self.db = db
        self.business_id = 1

    # =====================================================
    # MAIN PROCESS
    # =====================================================

    def process(
        self,
        message: str,
        customer_phone: str | None = None,
        customer_name: str | None = None,
        customer_email: str | None = None,
        business_id: int | None = None,
    ):
        self.business_id = business_id or 1
        message = (message or "").strip()

        if not message:
            return {
                "intent": "UNKNOWN",
                "booked": False,
                "missing": [],
                "reply": "Please tell me how I can help you.",
            }

        intent = detect_intent(message)
        phone_key = customer_phone or "anonymous"

        # Load session memory
        previous = {}
        if customer_phone and customer_phone in self.pending_bookings:
            previous.update(self.pending_bookings[customer_phone])
        if "anonymous" in self.pending_bookings:
            for k, v in self.pending_bookings["anonymous"].items():
                if previous.get(k) is None and v is not None:
                    previous[k] = v

        current_conv = previous.get("_conversation_type")

        # =====================================================
        # STATE OVERRIDE / TOPIC SWITCHING CHECK
        # =====================================================
        information_intents = [
            "SERVICE_PRICE", "SERVICE_DURATION", "SERVICE_LIST", "SERVICE_DETAILS",
            "BUSINESS_HOURS", "BUSINESS_INFORMATION", "CONTACT_BUSINESS",
            "DEPOSIT_INFORMATION", "LATE_ARRIVAL", "CANCELLATION_POLICY",
            "GROUP_BOOKING", "STAFF_SEARCH", "DOCTOR_SEARCH", "DOCTOR_SERVICES",
            "EMERGENCY_REQUEST", "FAQ", "THANK_YOU", "WHO_ARE_YOU",
            "HELP", "GOODBYE", "GREETING", "HOW_ARE_YOU", "ACKNOWLEDGEMENT",
            "AFFIRMATION_NO", "SWITCH_BUSINESS"
        ]

        if intent in information_intents and not any(w in message.lower() for w in ["confirm", "book it", "yes", "proceed"]):
            # Answer information query directly without losing pending booking state
            info_response = self.handle_information_query(intent, message)
            if info_response:
                return info_response

        if intent == "SWITCH_BUSINESS":
            self.pending_bookings[phone_key] = {"select_business_type": True}
            return {
                "intent": "SWITCH_BUSINESS",
                "booked": False,
                "missing": ["business_type"],
                "reply": "Sure! Please select or type the **type of business** you would like to switch to:",
                "options": [
                    "💇 Salon & Beauty Spa",
                    "🩺 Medical Clinic & Healthcare",
                    "💒 Event Management & Weddings",
                    "🏢 Real Estate & Property",
                    "📸 Photography & Studio",
                    "🏋️ Fitness & Gym Studio",
                    "🚗 Auto Repair & Garage",
                    "💬 Other (Type your own)"
                ]
            }

        if previous.get("_awaiting_cancel") or intent == "CANCEL_APPOINTMENT":
            return self.handle_cancel_appointment(message, customer_phone)

        if intent == "RESCHEDULE_APPOINTMENT":
            return self.handle_reschedule_appointment(message, customer_phone)

        if intent == "MY_APPOINTMENTS":
            return self.handle_my_appointments(customer_phone)

        # =====================================================
        # BOOKING / AVAILABILITY FLOW
        # =====================================================

        details = self.extract_booking_details(message)

        # Merge previous memory
        for key, val in previous.items():
            if not key.startswith("_") and val is not None:
                if details.get(key) is None:
                    details[key] = val

        biz_info = get_business_info(self.db, self.business_id)
        biz_name = biz_info.name if biz_info else "Business"
        details["active_business_type"] = biz_info.category if biz_info else "General"

        # Handle registration check
        awaiting_reg = previous.get("_awaiting_reg_field")

        # Validate step response if awaiting a specific registration field
        if awaiting_reg:
            if awaiting_reg == "full_name" and not previous.get("reg_name"):
                valid, err = is_valid_name(message)
                if not valid:
                    return {
                        "intent": "BOOK_APPOINTMENT",
                        "booked": False,
                        "missing": ["full name"],
                        "next_step": "reg_full_name",
                        "reply": f"⚠️ **Invalid Full Name**: {err}\n\nPlease provide a valid **Full Name** (e.g. Ram Sharma):",
                        "options": []
                    }
            elif awaiting_reg == "contact_number" and not previous.get("reg_phone"):
                valid, err = is_valid_phone(message)
                if not valid:
                    return {
                        "intent": "BOOK_APPOINTMENT",
                        "booked": False,
                        "missing": ["contact number"],
                        "next_step": "reg_contact_number",
                        "reply": f"⚠️ **Invalid Contact Number**: {err}\n\nPlease provide a valid **10-digit mobile number** (e.g. 9876543210):",
                        "options": []
                    }
            elif awaiting_reg in ["email_ID", "email_id", "email"] and not previous.get("reg_email"):
                valid, err = is_valid_email(message)
                if not valid:
                    return {
                        "intent": "BOOK_APPOINTMENT",
                        "booked": False,
                        "missing": ["email ID"],
                        "next_step": "reg_email_ID",
                        "reply": f"⚠️ **Invalid Email Address**: {err}\n\nPlease provide a valid **Email ID** format (e.g. ram@example.com):",
                        "options": []
                    }

        extracted_reg = self.extract_registration_info(message, awaiting_field=awaiting_reg)

        typed_name = extracted_reg.get("name") or previous.get("reg_name")
        typed_phone = extracted_reg.get("phone") or previous.get("reg_phone")
        typed_email = extracted_reg.get("email") or previous.get("reg_email")

        reg_name = typed_name if typed_name else customer_name
        reg_phone = typed_phone if typed_phone else customer_phone
        reg_email = typed_email if typed_email else customer_email

        db_customer = None
        if reg_phone:
            db_customer = find_customer(self.db, self.business_id, reg_phone)

        registered_just_now = False

        if db_customer:
            if typed_name and typed_name != db_customer.name:
                db_customer.name = typed_name
            if typed_email and typed_email != db_customer.email:
                db_customer.email = typed_email
            self.db.commit()
            self.db.refresh(db_customer)

            reg_name = db_customer.name
            reg_phone = db_customer.phone
            reg_email = db_customer.email or reg_email
            customer_phone = reg_phone
            customer_name = reg_name
        else:
            missing_reg = []
            if not reg_name:
                missing_reg.append("full name")
            if not reg_phone:
                missing_reg.append("contact number")
            if not reg_email:
                missing_reg.append("email ID")

            if missing_reg:
                details["_conversation_type"] = "booking"
                details["reg_name"] = reg_name
                details["reg_phone"] = reg_phone
                details["reg_email"] = reg_email
                next_reg = missing_reg[0]
                details["_awaiting_reg_field"] = next_reg.replace(" ", "_")

                self._save_session(phone_key, reg_phone, details)

                if next_reg == "full name":
                    prompt_msg = f"Welcome to **{biz_name}**! 👋 To complete your registration and book your appointment, what is your **Full Name**?"
                elif next_reg == "contact number":
                    prompt_msg = f"Thank you {reg_name or ''}! 📱 What is your **Contact Number** (phone number)?"
                else:
                    prompt_msg = f"Got it {reg_name or ''}! 📧 What is your **Email ID** so we can send your booking confirmation & reminders?"

                return {
                    "intent": "BOOK_APPOINTMENT",
                    "booked": False,
                    "missing": missing_reg,
                    "next_step": f"reg_{next_reg.replace(' ', '_')}",
                    "reply": prompt_msg,
                    "options": []
                }
            else:
                db_customer = create_customer(
                    self.db,
                    self.business_id,
                    reg_name,
                    reg_phone,
                    reg_email
                )
                registered_just_now = True
                customer_phone = reg_phone
                customer_name = reg_name

        details["reg_name"] = reg_name
        details["reg_phone"] = reg_phone
        details["reg_email"] = reg_email

        # Default guests & venue
        if not details.get("guests"):
            details["guests"] = 1
        if not details.get("venue"):
            details["venue"] = biz_name

        # Missing booking fields check
        missing = []
        if not details.get("event_type"):
            missing.append("service")
        if not details.get("appointment_date"):
            missing.append("appointment date")
        if not details.get("appointment_time"):
            missing.append("appointment time")

        welcome_banner = f"🎉 Welcome **{reg_name}**! Your account has been registered successfully with email **{reg_email}**.\n\n" if registered_just_now else ""

        if missing:
            details["_conversation_type"] = "booking"
            self._save_session(phone_key, customer_phone, details)

            if not details.get("appointment_date") and details.get("event_type"):
                options = self.available_date_options()
                return {
                    "intent": "BOOK_APPOINTMENT",
                    "booked": False,
                    "missing": missing,
                    "options": options,
                    "next_step": "appointment_date",
                    "reply": self._options_text(
                        options,
                        f"{welcome_banner}I checked the schedule for **{biz_name}**. Here are the available dates:"
                    ),
                }

            if details.get("appointment_date") and not details.get("appointment_time"):
                options = self.available_time_options(details["appointment_date"])
                if options:
                    return {
                        "intent": "BOOK_APPOINTMENT",
                        "booked": False,
                        "missing": missing,
                        "options": options,
                        "next_step": "appointment_time",
                        "reply": self._options_text(
                            options,
                            f"{welcome_banner}{self._format_date(details['appointment_date'])} has these available times for **{biz_name}**:"
                        ),
                    }

            next_field = missing[0]
            field_opts = self.get_options_for_field(next_field, details, active_biz=details.get("active_business_type"))
            return {
                "intent": "BOOK_APPOINTMENT",
                "booked": False,
                "missing": missing,
                "options": field_opts,
                "next_step": next_field.replace(" ", "_"),
                "reply": f"{welcome_banner}{self.ask_for_field(next_field, biz_name=biz_name)}",
            }

        # Check DB Availability
        staff_id = details.get("staff_id")
        service_names = details.get("service_names") or [details.get("event_type")]

        is_avail = check_availability(
            db=self.db,
            business_id=self.business_id,
            appointment_date=details["appointment_date"],
            appointment_time=details["appointment_time"],
            staff_id=staff_id,
            service_names=service_names,
            party_size=details.get("guests", 1)
        )

        if not is_avail:
            details["_conversation_type"] = "booking"
            self._save_session(phone_key, customer_phone, details)
            options = self.available_time_options(details["appointment_date"])
            return {
                "intent": "BOOK_APPOINTMENT",
                "booked": False,
                "missing": [],
                "options": options,
                "reply": self._options_text(
                    options,
                    f"{welcome_banner}That requested slot at **{biz_name}** is already booked or unavailable. Available times:"
                ),
            }

        # Calculate Price & Deposit
        price_info = calculate_price(self.db, self.business_id, service_names)
        deposit_info = calculate_deposit(self.db, self.business_id, service_names)

        # Complete Booking
        appointment = book_appointment(
            db=self.db,
            business_id=self.business_id,
            customer_id=db_customer.id,
            event_type=details["event_type"],
            appointment_date=details["appointment_date"],
            appointment_time=details["appointment_time"],
            venue=details["venue"],
            guests=details["guests"],
            notes=details.get("notes"),
            staff_id=staff_id
        )

        create_appointment_reminders(appointment, self.db)

        # Generate PDF Confirmation Pass
        from app.services.pdf_service import generate_appointment_pdf
        from app.services.whatsapp_provider import RSLWhatsAppProvider

        pdf_filepath, pdf_url = generate_appointment_pdf(self.db, appointment)

        # Dispatch live SMS/WhatsApp notification with PDF document to customer's mobile number
        try:
            whatsapp_msg = (
                f"🎉 APPOINTMENT CONFIRMED!\n\n"
                f"Dear {db_customer.name},\n"
                f"Your appointment for '{appointment.event_type}' at {biz_name} is confirmed!\n\n"
                f"🆔 Pass ID: GC-PASS-{appointment.id:05d}\n"
                f"📅 Date: {self._format_date(appointment.appointment_date)}\n"
                f"⏰ Time: {self._format_time(appointment.appointment_time)}\n"
                f"💰 Total Price: {biz_info.currency or '₹'}{price_info['total_price']:.2f}\n\n"
                f"📄 Your Official Appointment PDF Pass has been attached directly to this message.\n\n"
                f"Thank you for choosing {biz_name}!"
            )
            RSLWhatsAppProvider().send(db_customer, appointment, whatsapp_msg, pdf_url=pdf_url, pdf_filepath=pdf_filepath)
        except Exception as e:
            print(f"[PDF WhatsApp Dispatch Notice]: {e}")

        # Clear session
        self.pending_bookings.pop(phone_key, None)
        if customer_phone:
            self.pending_bookings.pop(customer_phone, None)
        self.pending_bookings.pop("anonymous", None)

        staff_str = f" with {details['staff_name']}" if details.get('staff_name') else ""
        deposit_str = f"\n\n💳 **Deposit Notice**: A deposit of {biz_info.currency or '₹'}{deposit_info['total_deposit']:.2f} is required for this service." if deposit_info["deposit_required"] else ""

        return {
            "intent": "BOOK_APPOINTMENT",
            "booked": True,
            "appointment_id": appointment.id,
            "pdf_url": pdf_url,
            "missing": [],
            "reply": (
                f"{welcome_banner}✅ **Booking Confirmed!**\n\n"
                f"🏢 **Business**: {biz_name}\n"
                f"🎉 **Service**: {appointment.event_type}\n"
                f"👤 **Staff**: {details.get('staff_name', 'Any Available Specialist')}\n"
                f"📅 **Date**: {self._format_date(appointment.appointment_date)}\n"
                f"⏰ **Time**: {self._format_time(appointment.appointment_time)}\n"
                f"⏱️ **Duration**: {price_info['total_duration']} minutes\n"
                f"💰 **Total Price**: {biz_info.currency or '₹'}{price_info['total_price']:.2f}"
                f"{deposit_str}\n\n"
                f"📄 **Official Appointment Pass (PDF attached below)**\n\n"
                f"📱 *Your confirmation PDF pass has been sent directly to your mobile number ({db_customer.phone}) via WhatsApp!*"
            ),
        }

    # =====================================================
    # INFORMATION QUERY HANDLER
    # =====================================================

    def handle_information_query(self, intent: str, message: str) -> dict | None:
        biz_info = get_business_info(self.db, self.business_id)
        if not biz_info:
            return None

        currency = biz_info.currency or "₹"
        biz_name = biz_info.name

        if intent == "SERVICE_LIST":
            services = get_services(self.db, self.business_id)
            lines = [f"💇 **{biz_name} - Services Catalog & Pricing**:\n"]
            for s in services:
                lines.append(f"• **{s.name}** ({s.duration_minutes} mins) - {currency}{float(s.price):.0f}")
            return {
                "intent": "SERVICE_LIST",
                "booked": False,
                "missing": [],
                "reply": "\n".join(lines),
                "options": [f"{s.name} ({currency}{float(s.price):.0f})" for s in services] + ["💬 Other (Type your own)"]
            }

        elif intent in ["SERVICE_PRICE", "SERVICE_DURATION"]:
            services = get_services(self.db, self.business_id)
            matched = []
            for s in services:
                if s.name.lower() in message.lower():
                    matched.append(s)

            if matched:
                lines = [f"💰 **Pricing & Duration at {biz_name}**:\n"]
                for s in matched:
                    lines.append(f"• **{s.name}**: {currency}{float(s.price):.0f} ({s.duration_minutes} minutes)")
                return {
                    "intent": intent,
                    "booked": False,
                    "missing": [],
                    "reply": "\n".join(lines),
                    "options": [f"{s.name} ({currency}{float(s.price):.0f})" for s in matched] + ["📅 Book Appointment", "💬 Other (Type your own)"]
                }
            else:
                lines = [f"Here are our key services & prices at **{biz_name}**:\n"]
                for s in services[:6]:
                    lines.append(f"• **{s.name}**: {currency}{float(s.price):.0f} ({s.duration_minutes} mins)")
                return {
                    "intent": intent,
                    "booked": False,
                    "missing": [],
                    "reply": "\n".join(lines),
                    "options": [f"{s.name} ({currency}{float(s.price):.0f})" for s in services[:5]] + ["📅 Book Appointment", "💬 Other (Type your own)"]
                }

        elif intent == "BUSINESS_INFORMATION":
            return {
                "intent": "BUSINESS_INFORMATION",
                "booked": False,
                "missing": [],
                "reply": f"🏢 **{biz_name}**\n\n{biz_info.description or 'Welcome!'}\n📍 **Location**: {biz_info.location}\n🕒 **Hours**: {biz_info.operating_hours}\n🅿️ **Amenities**: Free Parking & Wi-Fi available",
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            }

        elif intent == "CONTACT_BUSINESS":
            return {
                "intent": "CONTACT_BUSINESS",
                "booked": False,
                "missing": [],
                "reply": f"📞 **Contact {biz_name}**:\n• **Phone**: {biz_info.phone}\n• **Location**: {biz_info.location}\n• **Hours**: {biz_info.operating_hours}",
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            }

        elif intent == "SERVICE_DETAILS":
            services = get_services(self.db, self.business_id)
            matched = [s for s in services if s.name.lower() in message.lower()]
            if not matched:
                matched = services[:3]
            lines = [f"ℹ️ **Service Details for {biz_name}**:\n"]
            for s in matched:
                dep_info = f" ({s.deposit_percentage}% deposit required)" if (s.deposit_percentage or 0) > 0 else ""
                lines.append(f"• **{s.name}**: {currency}{float(s.price):.0f} | {s.duration_minutes} mins{dep_info}\n  _{s.description or 'High-quality service'}_")
            return {
                "intent": "SERVICE_DETAILS",
                "booked": False,
                "missing": [],
                "reply": "\n".join(lines),
                "options": [f"{s.name} ({currency}{float(s.price):.0f})" for s in matched] + ["📅 Book Appointment", "💬 Other (Type your own)"]
            }

        elif intent == "BUSINESS_HOURS":
            return {
                "intent": "BUSINESS_HOURS",
                "booked": False,
                "missing": [],
                "reply": f"🕒 **{biz_name} Business Hours**:\n{biz_info.operating_hours}\n\nAppointments are recommended. Walk-ins are subject to availability.",
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            }

        elif intent == "DEPOSIT_INFORMATION":
            return {
                "intent": "DEPOSIT_INFORMATION",
                "booked": False,
                "missing": [],
                "reply": f"💳 **{biz_name} Deposit Policy**:\nServices such as Hair Coloring and Full Body Spa require a 20% advance deposit to confirm your booking.",
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            }

        elif intent == "LATE_ARRIVAL":
            return {
                "intent": "LATE_ARRIVAL",
                "booked": False,
                "missing": [],
                "reply": f"⏰ **{biz_name} Late Arrival Policy**:\nIf you are more than 15 minutes late, your appointment may be shortened or rescheduled based on staff availability.",
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            }

        elif intent == "CANCELLATION_POLICY":
            return {
                "intent": "CANCELLATION_POLICY",
                "booked": False,
                "missing": [],
                "reply": f"❌ **{biz_name} Cancellation Policy**:\nCancellations and rescheduling are allowed free of charge up to 4 hours prior to your scheduled slot.",
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            }

        elif intent == "GROUP_BOOKING":
            return {
                "intent": "GROUP_BOOKING",
                "booked": False,
                "missing": [],
                "reply": f"👥 **{biz_name} Group Booking Policy**:\nWe support group bookings for up to 4 people! You can specify the number of guests when making your appointment.",
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            }

        elif intent == "EMERGENCY_REQUEST":
            return {
                "intent": "EMERGENCY_REQUEST",
                "booked": False,
                "missing": [],
                "reply": "🚨 **Emergency Medical Notice**:\n\nIf this is a medical emergency, please contact emergency medical services (108/112) or go to the nearest emergency department immediately. I can help with routine appointment bookings but cannot handle emergency medical care.",
                "options": ["📞 Contact Clinic", "📅 Book Appointment", "💬 Other (Type your own)"]
            }

        elif intent in ["STAFF_SEARCH", "DOCTOR_SEARCH", "DOCTOR_SERVICES"]:
            staff_members = get_staff(self.db, self.business_id)
            msg_lower = message.lower().strip()
            
            # Check for specific doctor or specialization match
            matched_staff = []
            for st in staff_members:
                role_lower = (st.role or "").lower()
                name_lower = (st.name or "").lower()
                services_lower = (st.supported_services or "").lower()
                
                if (
                    name_lower in msg_lower or 
                    role_lower in msg_lower or 
                    any(term in msg_lower for term in role_lower.split() if len(term) > 3) or
                    ("physician" in msg_lower and "physician" in role_lower) or
                    ("dermatologist" in msg_lower and "dermatol" in role_lower) or
                    ("child" in msg_lower and ("pediatric" in role_lower or "pediatric" in services_lower)) or
                    ("pediatrician" in msg_lower and "pediatric" in role_lower) or
                    ("dental" in msg_lower and ("dentist" in role_lower or "dental" in services_lower)) or
                    ("physiotherapy" in msg_lower and ("physio" in role_lower or "physio" in services_lower))
                ):
                    matched_staff.append(st)

            if matched_staff and len(matched_staff) == 1:
                st = matched_staff[0]
                services_str = f" provides {st.supported_services}" if st.supported_services else ""
                reply_text = f"👨‍⚕️ **{st.name}** is our **{st.role}** at {biz_name}.{services_str}\n\nWould you like to check available slots or book an appointment with {st.name}?"
                options = [f"📅 Book with {st.name}", "⏰ Check Available Slots", "💬 Other (Type your own)"]
            elif matched_staff and len(matched_staff) > 1:
                lines = [f"👨‍⚕️ **Matching Specialists at {biz_name}**:\n"]
                for st in matched_staff:
                    services_str = f" ({st.supported_services})" if st.supported_services else ""
                    lines.append(f"• **{st.name}** - {st.role}{services_str}")
                reply_text = "\n".join(lines)
                options = [f"📅 Book with {st.name}" for st in matched_staff[:3]] + ["💬 Other (Type your own)"]
            else:
                lines = [f"👨‍⚕️ **Our Specialists & Doctors at {biz_name}**:\n"]
                for st in staff_members:
                    services_str = f" ({st.supported_services})" if st.supported_services else ""
                    lines.append(f"• **{st.name}** - {st.role}{services_str}")
                reply_text = "\n".join(lines)
                options = [f"📅 Book with {st.name}" for st in staff_members[:4]] + ["💬 Other (Type your own)"]

            return {
                "intent": intent,
                "booked": False,
                "missing": [],
                "reply": reply_text,
                "options": options
            }

        elif intent in ["GREETING", "THANK_YOU", "WHO_ARE_YOU", "HELP", "HOW_ARE_YOU", "ACKNOWLEDGEMENT", "GOODBYE", "AFFIRMATION_NO"]:
            msg_lower = (message or "").lower().strip()

            if intent == "GREETING":
                if "morning" in msg_lower:
                    reply_msg = f"Good morning! ☀️ Warm greetings from **{biz_name}**!\nHow can I assist you today?"
                elif "afternoon" in msg_lower:
                    reply_msg = f"Good afternoon! 🌤️ Welcome to **{biz_name}**!\nHow can I help you today?"
                elif "evening" in msg_lower:
                    reply_msg = f"Good evening! 🌙 Welcome to **{biz_name}**!\nHow can I assist you today?"
                else:
                    reply_msg = f"Hello! 👋 Warm greetings from **{biz_name}**!\n\nHow can I help you today? You can book an appointment, check available slots, view pricing, or ask any questions!"

            elif intent == "ACKNOWLEDGEMENT":
                if any(w in msg_lower for w in ["thank", "thx", "thnks"]):
                    reply_msg = f"You're very welcome! 😊 Glad I could help. Let me know whenever you'd like to book an appointment or ask anything about **{biz_name}**!"
                elif any(w in msg_lower for w in ["great", "awesome", "perfect", "cool", "nice"]):
                    reply_msg = f"Awesome! 😊 I'm right here whenever you're ready to book an appointment or check available slots at **{biz_name}**."
                else:
                    reply_msg = f"Sounds great! 👍 Feel free to let me know whenever you'd like to schedule an appointment, check prices, or if you have any questions about **{biz_name}**."

            elif intent == "HOW_ARE_YOU":
                reply_msg = f"I'm doing great, thank you for asking! 😊 I'm all set to assist you with appointments, available slots, and pricing at **{biz_name}**.\n\nHow can I help you today?"

            elif intent == "THANK_YOU":
                reply_msg = f"You're so welcome! 😊 It's a true pleasure to assist you at **{biz_name}**. Feel free to reach out anytime if you need anything else!"

            elif intent == "GOODBYE":
                reply_msg = f"Goodbye! 👋 Have a wonderful day ahead! Feel free to chat with me anytime you need an appointment at **{biz_name}**."

            elif intent == "AFFIRMATION_NO":
                reply_msg = f"No problem at all! 👍 I'm right here if you need anything else or want to book an appointment later."

            elif intent == "WHO_ARE_YOU":
                reply_msg = f"I'm the AI Booking & Customer Assistant for **{biz_name}** 🤖! I can help you schedule appointments, check slot availability, view prices, and manage bookings."

            else:
                reply_msg = f"I'd be happy to help you with **{biz_name}**!\n\n• 📅 Book appointments\n• ⏰ Check slot availability\n• 💰 View services & prices\n• 👤 Choose preferred staff\n• 🔄 Modify or cancel bookings"

            return {
                "intent": intent,
                "booked": False,
                "missing": [],
                "reply": reply_msg,
                "options": ["📅 Book Appointment", "⏰ Check Available Slots", "💇 Services Catalog", "💬 Other (Type your own)"]
            }

        return None

    # =====================================================
    # SESSION SAVE HELPER
    # =====================================================

    def _save_session(self, phone_key: str, customer_phone: str | None, details: dict):
        self.pending_bookings[phone_key] = details
        self.pending_bookings["anonymous"] = details
        if customer_phone:
            self.pending_bookings[customer_phone] = details

    # =====================================================
    # ENTITY EXTRACTION HELPERS
    # =====================================================

    def extract_booking_details(self, message: str) -> dict:
        text = message.lower().strip()
        clean_text = re.sub(r'\s*\([\₹\$\€\£a-zA-Z0-9\s\.\,\:\-]*\)', '', text).strip()

        # Extract services (supporting multi-service)
        services = get_services(self.db, self.business_id)
        matched_services = []
        for s in services:
            s_name_lower = s.name.lower()
            if s_name_lower in text or s_name_lower in clean_text:
                matched_services.append(s.name)

        event_type = " + ".join(matched_services) if matched_services else self.extract_event_type(clean_text or text)

        # Extract staff
        staff_members = get_staff(self.db, self.business_id)
        matched_staff = None
        matched_staff_id = None
        for st in staff_members:
            if st.name.lower() in text:
                matched_staff = st.name
                matched_staff_id = st.id
                break

        appointment_date = self.extract_date(text)
        appointment_time = self.extract_time(text)
        guests = self.extract_guests(text)

        return {
            "event_type": event_type,
            "service_names": matched_services if matched_services else ([event_type] if event_type else []),
            "staff_name": matched_staff,
            "staff_id": matched_staff_id,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "guests": guests,
            "venue": None,
            "notes": None,
        }

    # =====================================================
    # REGISTRATION INFO EXTRACTION
    # =====================================================

    def extract_registration_info(self, text: str, awaiting_field: str | None = None) -> dict:
        info = {}
        msg_str = (text or "").strip()

        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', msg_str)
        if email_match:
            cand_email = email_match.group(0)
            valid, _ = is_valid_email(cand_email)
            if valid:
                info["email"] = cand_email.lower()

        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{10,15}\b', msg_str)
        if phone_match:
            digits = re.sub(r'\D', '', phone_match.group(0))
            valid, _ = is_valid_phone(digits)
            if valid:
                info["phone"] = digits[-10:] if len(digits) >= 10 else digits

        name_match = re.search(r'(?:my name is|i am|call me|name is|name:)\s+([a-zA-Z\s]{2,50})', msg_str, re.IGNORECASE)
        if name_match:
            cand_name = name_match.group(1).strip().title()
            valid, _ = is_valid_name(cand_name)
            if valid:
                info["name"] = cand_name
        elif awaiting_field in ["full_name", "name", "reg_name"]:
            valid, _ = is_valid_name(msg_str)
            if valid:
                info["name"] = msg_str.strip().title()

        return info

    # =====================================================
    # DATE / TIME / EVENT EXTRACTION
    # =====================================================

    @staticmethod
    def extract_event_type(text: str):
        text_lower = text.lower()
        mapping = [
            (r"\b(haircut \+ beard|haircut and beard)\b", "Haircut + Beard"),
            (r"\b(haircut|hair trim)\b", "Haircut"),
            (r"\b(hair styling|styling)\b", "Hair Styling"),
            (r"\b(hair coloring|coloring|color)\b", "Hair Coloring"),
            (r"\b(facial|clean up|skin care)\b", "Facial"),
            (r"\b(cleanup)\b", "Cleanup"),
            (r"\b(manicure)\b", "Manicure"),
            (r"\b(pedicure)\b", "Pedicure"),
            (r"\b(head massage|massage)\b", "Head Massage"),
            (r"\b(full body spa|spa body|body spa)\b", "Full Body Spa"),
            (r"\b(hair spa)\b", "Hair Spa"),
            (r"\b(beard trim|beard)\b", "Beard Trim"),
            (r"\b(general consultation|consultation)\b", "General Consultation"),
            (r"\b(dental consultation|dental|teeth)\b", "Dental Consultation"),
        ]
        for pattern, event_name in mapping:
            if re.search(pattern, text_lower):
                return event_name
        return None

    @staticmethod
    def extract_date(text: str):
        today = date.today()
        text_lower = text.lower().strip()

        if re.search(r"\btoday\b", text_lower):
            return today
        if re.search(r"\bday after tomorrow\b", text_lower):
            return today + timedelta(days=2)
        if re.search(r"\btomorrow\b|kal|udya", text_lower):
            return today + timedelta(days=1)
        if re.search(r"\bnext week\b", text_lower):
            return today + timedelta(days=7)

        months_map = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
        }
        months_pat = r"(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sept|sep|october|oct|november|nov|december|dec)"

        # MONTH DD YYYY
        written_date = re.search(rf"\b{months_pat}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,\s*|\s+)(\d{{4}})\b", text_lower)
        if written_date:
            try:
                return date(int(written_date.group(3)), months_map[written_date.group(1)], int(written_date.group(2)))
            except (ValueError, KeyError):
                pass

        # DD MONTH YYYY
        reverse_date = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{months_pat}\s+(\d{{4}})\b", text_lower)
        if reverse_date:
            try:
                return date(int(reverse_date.group(3)), months_map[reverse_date.group(2)], int(reverse_date.group(1)))
            except (ValueError, KeyError):
                pass

        # ISO YYYY-MM-DD
        iso_match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text_lower)
        if iso_match:
            try:
                return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            except ValueError:
                pass

        weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        for day_name, target_day in weekdays.items():
            if re.search(rf"\b(next|this)?\s*{day_name}\b", text_lower):
                days_ahead = target_day - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return today + timedelta(days=days_ahead)

        return None

    @staticmethod
    def extract_time(text: str):
        text_lower = text.lower().strip()
        match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            period = match.group(3).lower()

            if 1 <= hour <= 12 and 0 <= minute <= 59:
                if period == "pm" and hour != 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0
                return datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").time()

        iso_time = re.search(r"\b(\d{1,2}):(\d{2})(?::\d{2})?\b", text_lower)
        if iso_time:
            h = int(iso_time.group(1))
            m = int(iso_time.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return datetime.strptime(f"{h:02d}:{m:02d}", "%H:%M").time()

        return None

    @staticmethod
    def extract_guests(text: str):
        text = text.lower().strip()
        match = re.search(r"\b(\d+)\s*(?:people|person|persons|guest|guests)\b", text)
        if match:
            val = int(match.group(1))
            return val if val <= 10 else 1
        standalone = re.fullmatch(r"\s*(\d{1,2})\s*", text)
        if standalone:
            val = int(standalone.group(1))
            if 1 <= val <= 10:
                return val
        return None

    # =====================================================
    # CANCEL & RESCHEDULE HELPERS
    # =====================================================

    def handle_cancel_appointment(self, message: str, customer_phone: str | None = None):
        phone_key = customer_phone or "anonymous"

        # 1. Check for Appointment ID in message (e.g., "#12", "id 12", "cancel 12", "cancel appointment 12")
        appt_id_match = re.search(r'(?:appointment|booking|id|#)\s*[:#]?\s*(\d+)', message, re.IGNORECASE)
        if not appt_id_match and re.match(r'^\s*#?(\d+)\s*$', message):
            appt_id_match = re.match(r'^\s*#?(\d+)\s*$', message)

        if appt_id_match:
            target_id = int(appt_id_match.group(1))
            appt = self.db.query(Appointment).filter(Appointment.id == target_id).first()
            if appt:
                if appt.status == "cancelled":
                    return {
                        "intent": "CANCEL_APPOINTMENT",
                        "booked": False,
                        "cancelled": True,
                        "appointment_id": appt.id,
                        "reply": f"ℹ️ Appointment #{appt.id} is already cancelled."
                    }
                cancel_appointment(self.db, appt)
                
                # Send WhatsApp cancellation notice
                try:
                    from app.services.whatsapp_provider import RSLWhatsAppProvider
                    customer = self.db.query(Customer).filter(Customer.id == appt.customer_id).first()
                    if customer:
                        cancel_msg = (
                            f"❌ APPOINTMENT CANCELLED\n\n"
                            f"Dear {customer.name},\n"
                            f"Your appointment #{appt.id} for '{appt.event_type}' on {appt.appointment_date} at {appt.appointment_time} has been cancelled.\n\n"
                            f"You can reschedule or book a new slot anytime on our booking page."
                        )
                        RSLWhatsAppProvider().send(customer, appt, cancel_msg)
                except Exception as e:
                    print(f"[WhatsApp Cancellation]: {e}")

                if phone_key in self.pending_bookings:
                    self.pending_bookings[phone_key].pop("_awaiting_cancel", None)

                return {
                    "intent": "CANCEL_APPOINTMENT",
                    "booked": False,
                    "cancelled": True,
                    "appointment_id": appt.id,
                    "reply": f"✅ Your appointment #{appt.id} for **{appt.event_type}** on **{self._format_date(appt.appointment_date)}** at **{self._format_time(appt.appointment_time)}** has been cancelled successfully."
                }

        # 2. Extract phone if not explicitly provided
        if not customer_phone:
            phone_m = re.search(r'\b(?:\+?91[-.\s]?)?([6-9]\d{9})\b', message)
            if not phone_m:
                phone_m = re.search(r'\b(\d{10})\b', message)
            if phone_m:
                customer_phone = phone_m.group(1)
                phone_key = customer_phone

        # 3. If still no phone, ask customer to type their phone number or booking ID
        if not customer_phone:
            if phone_key not in self.pending_bookings:
                self.pending_bookings[phone_key] = {}
            self.pending_bookings[phone_key]["_awaiting_cancel"] = True
            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": ["phone number"],
                "reply": "Please share your **registered mobile number** or **Booking ID** (e.g. '#12') so I can find and cancel your appointment."
            }

        # 4. Find customer by phone
        clean_phone = customer_phone.strip()
        customer = find_customer(self.db, self.business_id, clean_phone)
        if not customer:
            customer = self.db.query(Customer).filter(Customer.phone.contains(clean_phone)).first()

        if not customer:
            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": f"I couldn't find any booking record associated with phone number **{customer_phone}**."
            }

        appointments = get_customer_appointments(self.db, customer.id, include_cancelled=False)
        if self.business_id:
            biz_appts = [a for a in appointments if a.business_id == self.business_id]
            if biz_appts:
                appointments = biz_appts

        if not appointments:
            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": f"You don't have any active appointments scheduled under **{customer_phone}** to cancel."
            }

        # 5. If single active appointment, cancel directly
        if len(appointments) == 1:
            appt = appointments[0]
            cancel_appointment(self.db, appt)

            try:
                from app.services.whatsapp_provider import RSLWhatsAppProvider
                cancel_msg = (
                    f"❌ APPOINTMENT CANCELLED\n\n"
                    f"Dear {customer.name},\n"
                    f"Your appointment #{appt.id} for '{appt.event_type}' on {appt.appointment_date} at {appt.appointment_time} has been cancelled.\n\n"
                    f"You can reschedule or book a new slot anytime on our booking page."
                )
                RSLWhatsAppProvider().send(customer, appt, cancel_msg)
            except Exception as e:
                print(f"[WhatsApp Cancellation]: {e}")

            if phone_key in self.pending_bookings:
                self.pending_bookings[phone_key].pop("_awaiting_cancel", None)

            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "cancelled": True,
                "appointment_id": appt.id,
                "reply": f"✅ Your appointment #{appt.id} for **{appt.event_type}** on **{self._format_date(appt.appointment_date)}** at **{self._format_time(appt.appointment_time)}** has been cancelled successfully."
            }

        # 6. Multiple active appointments: provide selection options
        options = [f"Cancel #{a.id}: {a.event_type} ({self._format_date(a.appointment_date)})" for a in appointments]
        return {
            "intent": "CANCEL_APPOINTMENT",
            "booked": False,
            "missing": ["appointment choice"],
            "options": options,
            "reply": f"You have **{len(appointments)} active appointments**. Which one would you like to cancel? Please select or type the Booking ID:"
        }

    def handle_reschedule_appointment(self, message: str, customer_phone: str | None = None):
        if not customer_phone:
            return {"intent": "RESCHEDULE_APPOINTMENT", "booked": False, "missing": ["phone number"], "reply": "Please share your contact phone number to find your active appointment."}

        customer = find_customer(self.db, self.business_id, customer_phone)
        if not customer:
            return {"intent": "RESCHEDULE_APPOINTMENT", "booked": False, "missing": [], "reply": "I couldn't find an account associated with this phone number."}

        appointments = get_customer_appointments(self.db, customer.id, include_cancelled=False)
        if not appointments:
            return {"intent": "RESCHEDULE_APPOINTMENT", "booked": False, "missing": [], "reply": "You don't have any active appointments to reschedule."}

        new_d = self.extract_date(message)
        new_t = self.extract_time(message)

        if not new_d or not new_t:
            options = self.available_date_options()
            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "missing": ["new date and time"],
                "options": options,
                "reply": "Please provide the new date and time you would like to reschedule your appointment to."
            }

        appt = appointments[0]
        appt.appointment_date = new_d
        appt.appointment_time = new_t
        self.db.commit()
        self.db.refresh(appt)

        return {
            "intent": "RESCHEDULE_APPOINTMENT",
            "booked": False,
            "rescheduled": True,
            "appointment_id": appt.id,
            "reply": f"✅ Your appointment for **{appt.event_type}** has been rescheduled to **{self._format_date(new_d)}** at **{self._format_time(new_t)}**!"
        }

    def handle_my_appointments(self, customer_phone: str | None = None):
        if not customer_phone:
            return {"intent": "MY_APPOINTMENTS", "booked": False, "missing": ["phone number"], "reply": "Please share your contact phone number to list your appointments."}

        customer = find_customer(self.db, self.business_id, customer_phone)
        if not customer:
            return {"intent": "MY_APPOINTMENTS", "booked": False, "missing": [], "reply": "No active customer record found for this phone number."}

        appts = get_customer_appointments(self.db, customer.id, include_cancelled=False)
        if not appts:
            return {"intent": "MY_APPOINTMENTS", "booked": False, "missing": [], "reply": "You have no active appointments scheduled."}

        lines = ["📋 **Your Scheduled Appointments**:\n"]
        for a in appts:
            lines.append(f"• **ID {a.id}**: {a.event_type} on {self._format_date(a.appointment_date)} at {self._format_time(a.appointment_time)} (Status: {a.status})")

        return {"intent": "MY_APPOINTMENTS", "booked": False, "missing": [], "reply": "\n".join(lines)}

    # =====================================================
    # AVAILABILITY OPTIONS HELPERS
    # =====================================================

    def available_date_options(self, start_date=None):
        start_date = start_date or date.today()
        result = []
        for offset in range(30):
            cand = start_date + timedelta(days=offset)
            result.append({"type": "date", "label": self._format_date(cand), "value": cand.isoformat()})
            if len(result) >= self.MAX_SUGGESTED_DATES:
                break
        return result

    def available_time_options(self, appointment_date):
        times = ["10:00 AM", "11:00 AM", "01:00 PM", "02:00 PM", "03:00 PM", "04:00 PM", "05:00 PM", "06:00 PM"]
        return [{"type": "time", "label": t, "value": t} for t in times]

    def get_default_options_for_business(self, active_biz=None):
        services = get_services(self.db, self.business_id)
        if services:
            return [
                "📅 Book Appointment",
                "⏰ Check Available Slots",
                "💇 Services Catalog",
                "💬 Other (Type your own)"
            ]
        return [
            "📅 Book Appointment",
            "⏰ Check Available Slots",
            "💬 Other (Type your own)"
        ]

    def get_options_for_field(self, field, details=None, active_biz=None):
        services = get_services(self.db, self.business_id)
        biz_info = get_business_info(self.db, self.business_id)
        currency = (biz_info.currency if biz_info else "₹") or "₹"
        if field in ["service", "event type"]:
            return [f"{s.name} ({currency}{float(s.price):.0f})" for s in services] + ["💬 Other (Type your own)"]
        elif field == "appointment date":
            return self.available_date_options()
        elif field == "appointment time":
            return self.available_time_options(details.get("appointment_date") if details else None)
        return ["💬 Other (Type your own)"]

    def ask_for_field(self, field, biz_name="the business"):
        if field in ["service", "event type"]:
            services = get_services(self.db, self.business_id)
            biz_info = get_business_info(self.db, self.business_id)
            currency = (biz_info.currency if biz_info else "₹") or "₹"
            if services:
                service_lines = "\n".join([f"• **{s.name}** - {currency}{float(s.price):.0f} ({s.duration_minutes} mins)" for s in services])
                return f"Welcome to **{biz_name}**! 🎉 Here are our available services & prices:\n\n{service_lines}\n\nWhich service would you like to book today?"
            return f"Welcome to **{biz_name}**! 🎉 What service would you like to book today?"
        elif field == "appointment date":
            return "📅 What date would you like to schedule your appointment for? (e.g. tomorrow, next Saturday)"
        elif field == "appointment time":
            return "⏰ What time works best for you on that date?"
        return f"Please specify your {field}:"

    @staticmethod
    def _format_time(value):
        if hasattr(value, "strftime"):
            return value.strftime("%I:%M %p").lstrip("0")
        return str(value)

    @staticmethod
    def _format_date(value):
        if hasattr(value, "strftime"):
            return value.strftime("%A, %d %B %Y")
        return str(value)

    @staticmethod
    def _options_text(options, heading):
        if not options:
            return heading + "\nNo available slots found."
        return heading + "\n" + "\n".join(f"{i}. {o['label'] if isinstance(o, dict) else o}" for i, o in enumerate(options, 1)) + "\nPlease select an option."