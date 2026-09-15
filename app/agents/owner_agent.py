import re
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.models.business import Business
from app.models.service import Service
from app.models.staff import Staff
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.rule import BusinessRule


class OwnerAgent:
    def __init__(self, db: Session, business_id: int):
        self.db = db
        self.business_id = business_id

    def process(self, message: str) -> dict:
        msg = message.strip()
        msg_lower = msg.lower()

        biz = self.db.query(Business).filter(Business.id == self.business_id).first()
        if not biz:
            return {
                "reply": "Error: Business configuration not found. Please onboard your business first.",
                "action_taken": None
            }

        # -------------------------------------------------------------
        # 1. ADD SERVICE Intent
        # Example: "Add a haircut service for ₹400 and 30 minutes."
        # Example: "Add Haircut service for 500 price and 45 minutes"
        # -------------------------------------------------------------
        if ("add" in msg_lower or "create" in msg_lower) and ("service" in msg_lower or "offering" in msg_lower):
            # Parse price
            price_match = re.search(r'(?:₹|\$|rs\.?|inr)?\s*(\d+(?:\.\d{1,2})?)', msg_lower)
            price = float(price_match.group(1)) if price_match else 0.0

            # Parse duration
            duration_match = re.search(r'(\d+)\s*(?:mins?|minutes?)', msg_lower)
            duration = int(duration_match.group(1)) if duration_match else 30

            # Parse service name
            name = ""
            name_match = re.search(r'(?:add|create)\s+(?:a\s+|an\s+)?(.+?)\s+(?:service|for|at|\d)', msg, re.IGNORECASE)
            if name_match:
                name = name_match.group(1).strip()
            if not name or name.lower() in ["service", "a service", "new service"]:
                # Fallback clean extraction
                words = msg.split()
                name = "New Service"
                for i, w in enumerate(words):
                    if w.lower() in ["add", "create"] and i + 1 < len(words):
                        name = " ".join(words[i+1:i+3]).replace("service", "").strip()
                        break

            new_service = Service(
                business_id=biz.id,
                name=name.title(),
                category=biz.category,
                duration_minutes=duration,
                price=price,
                description=f"{name.title()} service added via Owner AI Assistant.",
                is_active=True
            )
            self.db.add(new_service)
            self.db.commit()
            self.db.refresh(new_service)

            return {
                "reply": f"✅ Service '{new_service.name}' registered successfully for {biz.currency} {new_service.price:.2f} ({new_service.duration_minutes} mins).",
                "action_taken": "ADD_SERVICE",
                "data": {"id": new_service.id, "name": new_service.name, "price": new_service.price, "duration": new_service.duration_minutes}
            }

        # -------------------------------------------------------------
        # 2. STAFF WORK SCHEDULE / ADD STAFF Intent
        # Example: "Priya works Monday to Saturday from 10 AM to 7 PM."
        # Example: "Add staff Rahul Senior Hair Stylist 10 AM to 6 PM"
        # -------------------------------------------------------------
        if any(kw in msg_lower for kw in ["works", "schedule", "working hours for", "shift"]) or (("add" in msg_lower or "create" in msg_lower) and ("staff" in msg_lower or "doctor" in msg_lower)):
            # Check for days match
            days_match = re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s*to\s*|\s*-\s*)(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', msg_lower)
            working_days = "Monday,Tuesday,Wednesday,Thursday,Friday,Saturday"
            if days_match:
                d1, d2 = days_match.group(1).title(), days_match.group(2).title()
                all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                if d1 in all_days and d2 in all_days:
                    idx1, idx2 = all_days.index(d1), all_days.index(d2)
                    if idx1 <= idx2:
                        working_days = ",".join(all_days[idx1:idx2+1])

            # Extract staff name
            words = msg.split()
            staff_name = "Staff Member"
            if "works" in msg_lower:
                staff_name = msg[:msg_lower.index("works")].replace("Add", "").replace("add", "").strip()
            elif "staff" in msg_lower:
                match = re.search(r'(?:staff|doctor)\s+([A-Za-z\s]+)', msg, re.IGNORECASE)
                if match:
                    staff_name = match.group(1).split()[0]

            staff_name = staff_name.title() or "Staff Member"

            # Parse times
            start_time = "10:00"
            end_time = "19:00"
            times = re.findall(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', msg_lower)
            if len(times) >= 2:
                # Format start
                h1, m1, p1 = int(times[0][0]), times[0][1] or "00", times[0][2]
                if p1 == "pm" and h1 < 12: h1 += 12
                if p1 == "am" and h1 == 12: h1 = 0
                start_time = f"{h1:02d}:{m1}"

                # Format end
                h2, m2, p2 = int(times[1][0]), times[1][1] or "00", times[1][2]
                if p2 == "pm" and h2 < 12: h2 += 12
                if p2 == "am" and h2 == 12: h2 = 0
                end_time = f"{h2:02d}:{m2}"

            stf = self.db.query(Staff).filter(Staff.business_id == biz.id, Staff.name.ilike(f"%{staff_name}%")).first()
            if not stf:
                stf = Staff(
                    business_id=biz.id,
                    name=staff_name,
                    role="Specialist",
                    working_days=working_days,
                    working_start=start_time,
                    working_end=end_time,
                    is_active=True
                )
                self.db.add(stf)
            else:
                stf.working_days = working_days
                stf.working_start = start_time
                stf.working_end = end_time

            self.db.commit()
            self.db.refresh(stf)

            return {
                "reply": f"✅ Schedule for {stf.name} updated: Working days ({stf.working_days}) from {stf.working_start} to {stf.working_end}.",
                "action_taken": "UPDATE_STAFF",
                "data": {"id": stf.id, "name": stf.name, "working_days": stf.working_days, "start": stf.working_start, "end": stf.working_end}
            }

        # -------------------------------------------------------------
        # 3. QUERY BUSINESS HOURS
        # Example: "What are my business hours?"
        # -------------------------------------------------------------
        if any(phrase in msg_lower for phrase in ["business hours", "operating hours", "working hours", "opening hours"]):
            return {
                "reply": f"🏢 Operating Hours for '{biz.name}': {biz.operating_hours} ({biz.timezone} timezone).",
                "action_taken": "GET_HOURS",
                "data": {"operating_hours": biz.operating_hours, "timezone": biz.timezone}
            }

        # -------------------------------------------------------------
        # 4. QUERY TODAY'S OR UPCOMING APPOINTMENTS
        # Example: "Show me today's appointments." / "List appointments"
        # -------------------------------------------------------------
        if "appointment" in msg_lower or "booking" in msg_lower:
            today_str = date.today().isoformat()
            if "today" in msg_lower:
                appts = self.db.query(Appointment).filter(
                    Appointment.business_id == biz.id,
                    Appointment.appointment_date == date.today()
                ).all()
                period_name = "today"
            else:
                appts = self.db.query(Appointment).filter(
                    Appointment.business_id == biz.id
                ).order_by(Appointment.appointment_date.desc(), Appointment.appointment_time.asc()).limit(10).all()
                period_name = "recent/upcoming"

            if not appts:
                return {
                    "reply": f"📅 No appointments found for {period_name} at '{biz.name}'.",
                    "action_taken": "GET_APPOINTMENTS",
                    "data": {"count": 0, "appointments": []}
                }

            lines = [f"📅 Found {len(appts)} appointment(s) for {period_name}:"]
            for a in appts:
                cust_name = a.customer.name if a.customer else "Guest"
                lines.append(f"• ID #{a.id} - {cust_name} | {a.event_type} | {a.appointment_date} at {a.appointment_time.strftime('%I:%M %p')} | Status: {a.status.title()}")

            return {
                "reply": "\n".join(lines),
                "action_taken": "GET_APPOINTMENTS",
                "data": {"count": len(appts), "appointments": [{"id": a.id, "event_type": a.event_type, "date": str(a.appointment_date), "time": str(a.appointment_time), "status": a.status} for a in appts]}
            }

        # -------------------------------------------------------------
        # 5. QUERY SERVICES COUNT / LIST SERVICES
        # Example: "How many services do I currently offer?" / "List services"
        # -------------------------------------------------------------
        if "service" in msg_lower or "offering" in msg_lower or "catalog" in msg_lower:
            services = self.db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).all()
            if not services:
                return {
                    "reply": f"🛍️ You currently offer 0 services at '{biz.name}'. You can add services by saying 'Add a Haircut service for ₹400 and 30 minutes'.",
                    "action_taken": "GET_SERVICES",
                    "data": {"count": 0, "services": []}
                }

            lines = [f"🛍️ '{biz.name}' currently offers {len(services)} service(s):"]
            for s in services:
                lines.append(f"• {s.name} - {biz.currency} {float(s.price or 0):.2f} ({s.duration_minutes} mins)")

            return {
                "reply": "\n".join(lines),
                "action_taken": "GET_SERVICES",
                "data": {"count": len(services), "services": [{"id": s.id, "name": s.name, "price": float(s.price or 0), "duration": s.duration_minutes} for s in services]}
            }

        # -------------------------------------------------------------
        # 6. BUSINESS OVERVIEW / STATS
        # Example: "Show business summary" / "Stats"
        # -------------------------------------------------------------
        if any(w in msg_lower for w in ["stats", "summary", "overview", "count", "metrics"]):
            service_count = self.db.query(Service).filter(Service.business_id == biz.id, Service.is_active == True).count()
            staff_count = self.db.query(Staff).filter(Staff.business_id == biz.id, Staff.is_active == True).count()
            customer_count = self.db.query(Customer).filter(Customer.business_id == biz.id).count()
            appt_count = self.db.query(Appointment).filter(Appointment.business_id == biz.id).count()

            return {
                "reply": f"📊 Business Summary for '{biz.name}':\n• Total Appointments: {appt_count}\n• Services Offered: {service_count}\n• Active Staff/Doctors: {staff_count}\n• Total Registered Customers: {customer_count}\n• Status: {biz.status.title()}",
                "action_taken": "GET_STATS",
                "data": {"appointments": appt_count, "services": service_count, "staff": staff_count, "customers": customer_count}
            }

        # -------------------------------------------------------------
        # 7. DEFAULT HELPFUL RESPONSE
        # -------------------------------------------------------------
        return {
            "reply": f"🤖 I'm your Owner AI Assistant for '{biz.name}'. You can ask me:\n• 'Add a haircut service for ₹400 and 30 minutes'\n• 'Priya works Monday to Saturday from 10 AM to 7 PM'\n• 'What are my business hours?'\n• 'Show me today's appointments'\n• 'How many services do I currently offer?'",
            "action_taken": "HELP"
        }
