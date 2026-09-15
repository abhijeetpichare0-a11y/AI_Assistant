

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Appointment, Reminder

from app.agents.intent_detector import detect_intent

from app.agents.tools import (
    book_appointment,
    cancel_appointment,
    check_availability,
    create_customer,
    find_customer,
    get_appointment_by_id,
    get_customer_appointments,
)

from app.services.reminder_service import (
    create_appointment_reminders,
)


class AppointmentAgent:
    """
    AI Appointment Agent

    Handles:
    - Appointment booking
    - Availability checking
    - Appointment cancellation
    - Viewing customer appointments
    - Multi-turn conversation
    - Temporary conversation memory
    """

    # =====================================================
    # TEMPORARY CONVERSATION MEMORY
    # =====================================================

    pending_bookings = {}

    def __init__(self, db: Session):
        self.db = db

    # =====================================================
    # MAIN PROCESS
    # =====================================================

    def process(
        self,
        message: str,
        customer_phone: str | None = None,
        customer_name: str | None = None,
    ):
        message = (message or "").strip()

        # =================================================
        # EMPTY MESSAGE
        # =================================================

        if not message:
            return {
                "intent": "GENERAL_QUERY",
                "booked": False,
                "missing": [],
                "reply": "Please tell me how I can help you.",
            }

        # =================================================
        # DETECT USER INTENT
        # =================================================

        intent = detect_intent(message)

        # =================================================
        # CHECK ACTIVE CONVERSATION
        # =================================================

        has_pending_booking = (
            customer_phone
            and customer_phone in self.pending_bookings
        )

        # =================================================
        # CONTINUE RESCHEDULE CONVERSATION
        # =================================================

        if (
            has_pending_booking
            and self.pending_bookings[customer_phone].get(
                "_conversation_type"
            ) == "reschedule"
        ):
            return self.handle_reschedule_appointment(
                message,
                customer_phone,
            )

        # =================================================
        # CONTINUE CANCELLATION CONVERSATION
        # =================================================

        if (
            has_pending_booking
            and self.pending_bookings[customer_phone].get(
                "_conversation_type"
            ) == "cancellation"
        ):
            return self.handle_cancel_appointment(
                message,
                customer_phone,
            )

        # =================================================
        # MY APPOINTMENTS
        # =================================================

        if intent == "MY_APPOINTMENTS":
            return self.handle_my_appointments(
                customer_phone
            )

        # =================================================
        # CANCEL APPOINTMENT
        # =================================================

        if intent == "CANCEL_APPOINTMENT":
            return self.handle_cancel_appointment(
                message,
                customer_phone,
            )

        # =================================================
        # RESCHEDULE APPOINTMENT
        # =================================================

        if intent == "RESCHEDULE_APPOINTMENT":
            return self.handle_reschedule_appointment(
                message,
                customer_phone,
            )

        # =================================================
        # CHECK ACTIVE CONVERSATION
        # =================================================

        if has_pending_booking:

            previous = self.pending_bookings[
                customer_phone
            ]

            # =================================================
            # WAITING FOR BOOKING CONFIRMATION
            # =================================================

            if previous.get("_awaiting_confirmation"):

                normalized_message = (
                    message.lower().strip()
                )

                confirmation_words = [
                    "yes",
                    "yeah",
                    "yep",
                    "sure",
                    "ok",
                    "okay",
                    "book it",
                    "please book",
                    "confirm",
                    "confirmed",
                    "go ahead",
                ]

                rejection_words = [
                    "no",
                    "nope",
                    "not now",
                    "don't",
                    "do not",
                    "cancel",
                    "stop",
                ]

                # -------------------------------------------------
                # USER CONFIRMS
                # -------------------------------------------------

                if normalized_message in confirmation_words:

                    previous["_awaiting_confirmation"] = False
                    previous["_conversation_type"] = "booking"

                    details = {
                        key: value
                        for key, value in previous.items()
                        if not key.startswith("_")
                    }

                    self.pending_bookings[
                        customer_phone
                    ] = details

                    intent = "BOOK_APPOINTMENT"

                # -------------------------------------------------
                # USER REJECTS
                # -------------------------------------------------

                elif normalized_message in rejection_words:

                    self.pending_bookings.pop(
                        customer_phone,
                        None,
                    )

                    return {
                        "intent": "CHECK_AVAILABILITY",
                        "booked": False,
                        "missing": [],
                        "reply": (
                            "No problem. The available slot "
                            "has not been booked."
                        ),
                    }

                # -------------------------------------------------
                # USER SAYS SOMETHING ELSE
                # -------------------------------------------------

                else:

                    return {
                        "intent": "CHECK_AVAILABILITY",
                        "booked": False,
                        "missing": [],
                        "reply": (
                            "No problem. Let me know if you "
                            "would like to book the available slot."
                        ),
                    }

            # =================================================
            # CONTINUE EXISTING CONVERSATION
            # =================================================

            else:

                conversation_type = previous.get(
                    "_conversation_type"
                )

                # =================================================
                # AVAILABILITY CONVERSATION
                # =================================================

                if conversation_type == "availability":

                    return self.handle_availability(
                        message,
                        customer_phone,
                    )

                # =================================================
                # BOOKING CONVERSATION
                # =================================================

                if conversation_type == "booking":

                    if intent == "CHECK_AVAILABILITY":

                        return self.handle_availability(
                            message,
                            customer_phone,
                        )

                    intent = "BOOK_APPOINTMENT"

                # =================================================
                # UNKNOWN MEMORY
                # =================================================

                else:

                    if intent == "CHECK_AVAILABILITY":

                        return self.handle_availability(
                            message,
                            customer_phone,
                        )

                    intent = "BOOK_APPOINTMENT"

        # =================================================
        # NEW AVAILABILITY REQUEST
        # =================================================

        elif intent == "CHECK_AVAILABILITY":

            return self.handle_availability(
                message,
                customer_phone,
            )

        # =================================================
        # GENERAL QUERY
        # =================================================

        if intent == "GENERAL_QUERY":

            return {
                "intent": "GENERAL_QUERY",
                "booked": False,
                "missing": [],
                "reply": (
                    "Hello! 👋 I can help you book an "
                    "appointment, check availability, "
                    "or manage your event. "
                    "What would you like to do?"
                ),
            }

        # =================================================
        # OTHER INTENTS
        # =================================================

        if intent != "BOOK_APPOINTMENT":

            return {
                "intent": intent,
                "booked": False,
                "missing": [],
                "reply": (
                    f"I detected your request as "
                    f"{intent.replace('_', ' ').lower()}. "
                    "This operation will be added next."
                ),
            }

        # =================================================
        # BOOK APPOINTMENT
        # =================================================

        details = self.extract_booking_details(message)

        # =================================================
        # LOAD PREVIOUS MEMORY
        # =================================================

        if (
            customer_phone
            and customer_phone in self.pending_bookings
        ):

            previous = self.pending_bookings[
                customer_phone
            ]

            for key in details:

                if (
                    details[key] is None
                    and previous.get(key) is not None
                ):
                    details[key] = previous[key]

        # =================================================
        # PHONE REQUIRED
        # =================================================

        if not customer_phone:

            return {
                "intent": "BOOK_APPOINTMENT",
                "booked": False,
                "missing": ["phone number"],
                "reply": (
                    "I can help you book the appointment. "
                    "Please provide your phone number."
                ),
            }

        # =================================================
        # REQUIRED FIELDS
        # =================================================

        missing = []

        if not details["event_type"]:
            missing.append("event type")

        if not details["appointment_date"]:
            missing.append("appointment date")

        if not details["appointment_time"]:
            missing.append("appointment time")

        if not details["guests"]:
            missing.append("number of guests")

        # =================================================
        # VENUE IS CURRENTLY OPTIONAL
        # =================================================

        # Venue extraction can be improved later.

        # =================================================
        # PAST DATE VALIDATION
        # =================================================

        if details["appointment_date"]:

            if details["appointment_date"] < date.today():

                details["_conversation_type"] = "booking"

                self.pending_bookings[
                    customer_phone
                ] = details

                return {
                    "intent": "BOOK_APPOINTMENT",
                    "booked": False,
                    "missing": ["appointment date"],
                    "reply": (
                        "That date has already passed. "
                        "Please provide a future date."
                    ),
                }

        # =================================================
        # SAVE INCOMPLETE BOOKING
        # =================================================

        if missing:

            details["_conversation_type"] = "booking"

            self.pending_bookings[
                customer_phone
            ] = details

            next_field = missing[0]

            return {
                "intent": "BOOK_APPOINTMENT",
                "booked": False,
                "missing": missing,
                "reply": self.ask_for_field(
                    next_field
                ),
            }

        # =================================================
        # CHECK AVAILABILITY
        # =================================================

        available = check_availability(
            self.db,
            details["appointment_date"],
            details["appointment_time"],
        )

        # =================================================
        # SLOT NOT AVAILABLE
        # =================================================

        if not available:

            details["_conversation_type"] = "booking"

            self.pending_bookings[
                customer_phone
            ] = details

            return {
                "intent": "BOOK_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": (
                    "Sorry, that appointment slot is already "
                    "booked. Please choose another date or time."
                ),
            }

        # =================================================
        # FIND OR CREATE CUSTOMER
        # =================================================

        customer = find_customer(
            self.db,
            customer_phone,
        )

        if not customer:

            customer = create_customer(
                self.db,
                customer_name or "Customer",
                customer_phone,
            )

        # =================================================
        # CREATE APPOINTMENT
        # =================================================

        appointment = book_appointment(
            self.db,
            customer.id,
            details["event_type"],
            details["appointment_date"],
            details["appointment_time"],
            details["venue"],
            details["guests"],
            details["notes"],
        )

        # =================================================
        # CREATE REMINDERS
        # =================================================

        create_appointment_reminders(
            appointment,
            self.db,
        )

        # =================================================
        # CLEAR CONVERSATION MEMORY
        # =================================================

        self.pending_bookings.pop(
            customer_phone,
            None,
        )

        # =================================================
        # SUCCESS RESPONSE
        # =================================================

        return {
            "intent": "BOOK_APPOINTMENT",
            "booked": True,
            "appointment_id": appointment.id,
            "missing": [],
            "reply": (
                f"✅ Your {appointment.event_type} appointment "
                f"has been booked successfully for "
                f"{appointment.appointment_date} at "
                f"{appointment.appointment_time}. "
                f"Number of guests: {appointment.guests}."
            ),
        }

    # =====================================================
    # MY APPOINTMENTS
    # =====================================================

    def handle_my_appointments(
        self,
        customer_phone: str | None = None,
    ):
        """
        Show appointments belonging to the current customer.
        """

        # =================================================
        # PHONE REQUIRED
        # =================================================

        if not customer_phone:

            return {
                "intent": "MY_APPOINTMENTS",
                "booked": False,
                "missing": ["phone number"],
                "reply": (
                    "Please provide your phone number so "
                    "I can find your appointments."
                ),
            }

        # =================================================
        # FIND CUSTOMER
        # =================================================

        customer = find_customer(
            self.db,
            customer_phone,
        )

        if not customer:

            return {
                "intent": "MY_APPOINTMENTS",
                "booked": False,
                "missing": [],
                "reply": (
                    "I couldn't find any customer account "
                    "associated with this phone number."
                ),
            }

        # =================================================
        # GET APPOINTMENTS
        # =================================================

        appointments = get_customer_appointments(
            self.db,
            customer.id,
            include_cancelled=False,
        )

        # =================================================
        # NO APPOINTMENTS
        # =================================================

        if not appointments:

            return {
                "intent": "MY_APPOINTMENTS",
                "booked": False,
                "missing": [],
                "reply": (
                    "You don't have any active appointments "
                    "at the moment."
                ),
            }

        # =================================================
        # FORMAT APPOINTMENTS
        # =================================================

        lines = [
            "📋 Here are your appointments:"
        ]

        for appointment in appointments:

            appointment_line = (
                f"\n\n🆔 Appointment ID: {appointment.id}"
                f"\n🎉 Event: {appointment.event_type}"
                f"\n📅 Date: {appointment.appointment_date}"
                f"\n⏰ Time: {appointment.appointment_time}"
                f"\n👥 Guests: {appointment.guests}"
                f"\n📍 Venue: {appointment.venue}"
                f"\n📌 Status: {appointment.status}"
            )

            lines.append(
                appointment_line
            )

        return {
            "intent": "MY_APPOINTMENTS",
            "booked": False,
            "missing": [],
            "appointments": [
                {
                    "id": appointment.id,
                    "event_type": appointment.event_type,
                    "appointment_date": str(
                        appointment.appointment_date
                    ),
                    "appointment_time": str(
                        appointment.appointment_time
                    ),
                    "guests": appointment.guests,
                    "venue": appointment.venue,
                    "status": appointment.status,
                }
                for appointment in appointments
            ],
            "reply": "".join(lines),
        }

    # =====================================================
    # CANCEL APPOINTMENT
    # =====================================================

    def handle_cancel_appointment(
        self,
        message: str,
        customer_phone: str | None = None,
    ):
        """
        Handle appointment cancellation.
        """

        # =================================================
        # PHONE REQUIRED
        # =================================================

        if not customer_phone:

            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": ["phone number"],
                "reply": (
                    "Please provide your phone number so "
                    "I can find your appointment."
                ),
            }

        # =================================================
        # FIND CUSTOMER
        # =================================================

        customer = find_customer(
            self.db,
            customer_phone,
        )

        if not customer:

            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": (
                    "I couldn't find an account associated "
                    "with this phone number."
                ),
            }

        # =================================================
        # CHECK EXISTING CANCELLATION CONFIRMATION
        # =================================================

        pending = self.pending_bookings.get(
            customer_phone
        )

        if (
            pending
            and pending.get(
                "_awaiting_cancel_confirmation"
            )
        ):

            normalized = message.lower().strip()

            confirmation_words = [
                "yes",
                "yeah",
                "yep",
                "sure",
                "ok",
                "okay",
                "confirm",
                "confirmed",
                "cancel it",
                "yes cancel",
            ]

            rejection_words = [
                "no",
                "nope",
                "don't",
                "do not",
                "not now",
                "stop",
            ]

            # =================================================
            # CONFIRM CANCELLATION
            # =================================================

            if normalized in confirmation_words:

                appointment_id = pending.get(
                    "appointment_id"
                )

                appointment = get_appointment_by_id(
                    self.db,
                    appointment_id,
                    customer.id,
                )

                if not appointment:

                    self.pending_bookings.pop(
                        customer_phone,
                        None,
                    )

                    return {
                        "intent": "CANCEL_APPOINTMENT",
                        "booked": False,
                        "missing": [],
                        "reply": (
                            "I couldn't find that appointment. "
                            "It may have already been removed."
                        ),
                    }

                if appointment.status == "cancelled":

                    self.pending_bookings.pop(
                        customer_phone,
                        None,
                    )

                    return {
                        "intent": "CANCEL_APPOINTMENT",
                        "booked": False,
                        "missing": [],
                        "reply": (
                            "That appointment has already "
                            "been cancelled."
                        ),
                    }

                # =================================================
                # CANCEL
                # =================================================

                cancel_appointment(
                    self.db,
                    appointment,
                )

                self.pending_bookings.pop(
                    customer_phone,
                    None,
                )

                return {
                    "intent": "CANCEL_APPOINTMENT",
                    "booked": False,
                    "cancelled": True,
                    "appointment_id": appointment.id,
                    "missing": [],
                    "reply": (
                        f"✅ Your {appointment.event_type} "
                        f"appointment on "
                        f"{appointment.appointment_date} at "
                        f"{appointment.appointment_time} "
                        f"has been cancelled successfully."
                    ),
                }

            # =================================================
            # REJECT CANCELLATION
            # =================================================

            if normalized in rejection_words:

                self.pending_bookings.pop(
                    customer_phone,
                    None,
                )

                return {
                    "intent": "CANCEL_APPOINTMENT",
                    "booked": False,
                    "cancelled": False,
                    "missing": [],
                    "reply": (
                        "No problem. Your appointment has "
                        "not been cancelled."
                    ),
                }

            # =================================================
            # UNKNOWN RESPONSE
            # =================================================

            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": (
                    "Please confirm whether you want to "
                    "cancel this appointment. Reply "
                    "'yes' or 'no'."
                ),
            }

        # =================================================
        # GET ACTIVE APPOINTMENTS
        # =================================================

        appointments = get_customer_appointments(
            self.db,
            customer.id,
            include_cancelled=False,
        )

        if not appointments:

            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": (
                    "You don't have any active appointments "
                    "that can be cancelled."
                ),
            }

        # =================================================
        # TRY TO EXTRACT APPOINTMENT ID
        # =================================================

        appointment_id = self.extract_appointment_id(
            message
        )

        selected_appointment = None

        if appointment_id:

            selected_appointment = get_appointment_by_id(
                self.db,
                appointment_id,
                customer.id,
            )

            if (
                not selected_appointment
                or selected_appointment.status == "cancelled"
            ):

                return {
                    "intent": "CANCEL_APPOINTMENT",
                    "booked": False,
                    "missing": [],
                    "reply": (
                        f"I couldn't find an active "
                        f"appointment with ID "
                        f"{appointment_id}."
                    ),
                }

        # =================================================
        # ONLY ONE APPOINTMENT
        # =================================================

        elif len(appointments) == 1:

            selected_appointment = appointments[0]

        # =================================================
        # MULTIPLE APPOINTMENTS
        # =================================================

        else:

            lines = [
                "You have multiple active appointments. "
                "Please provide the Appointment ID you "
                "want to cancel:"
            ]

            for appointment in appointments:

                lines.append(
                    f"\n\n🆔 ID: {appointment.id}"
                    f"\n🎉 Event: {appointment.event_type}"
                    f"\n📅 Date: {appointment.appointment_date}"
                    f"\n⏰ Time: {appointment.appointment_time}"
                    f"\n👥 Guests: {appointment.guests}"
                )

            return {
                "intent": "CANCEL_APPOINTMENT",
                "booked": False,
                "missing": ["appointment id"],
                "reply": "".join(lines),
            }

        # =================================================
        # STORE CANCELLATION REQUEST
        # =================================================

        self.pending_bookings[
            customer_phone
        ] = {
            "_awaiting_cancel_confirmation": True,
            "_conversation_type": "cancellation",
            "appointment_id": selected_appointment.id,
        }

        # =================================================
        # ASK FOR CONFIRMATION
        # =================================================

        return {
            "intent": "CANCEL_APPOINTMENT",
            "booked": False,
            "appointment_id": selected_appointment.id,
            "missing": [],
            "reply": (
                f"Are you sure you want to cancel your "
                f"{selected_appointment.event_type} "
                f"appointment on "
                f"{selected_appointment.appointment_date} "
                f"at "
                f"{selected_appointment.appointment_time}? "
                f"Please reply 'yes' or 'no'."
            ),
        }

    # =====================================================
    # RESCHEDULE APPOINTMENT
    # =====================================================

    def handle_reschedule_appointment(
        self,
        message: str,
        customer_phone: str | None = None,
    ):
        """
        Reschedule an active customer appointment.

        The operation is intentionally confirmation-based:
        1. Identify the appointment.
        2. Collect the new date/time.
        3. Show the proposed change.
        4. Require explicit confirmation.
        5. Update the appointment and rebuild pending reminders.
        """

        if not customer_phone:
            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "missing": ["phone number"],
                "reply": (
                    "Please provide your phone number so I can "
                    "find the appointment you want to reschedule."
                ),
            }

        customer = find_customer(
            self.db,
            customer_phone,
        )

        if not customer:
            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": (
                    "I couldn't find an account associated with "
                    "this phone number."
                ),
            }

        pending = self.pending_bookings.get(customer_phone)
        normalized = (message or "").lower().strip()

        # -------------------------------------------------
        # CONFIRMATION OF A PENDING RESCHEDULE
        # -------------------------------------------------

        if pending and pending.get("_awaiting_reschedule_confirmation"):

            confirmation_words = {
                "yes", "yeah", "yep", "sure", "ok", "okay",
                "confirm", "confirmed", "do it", "go ahead",
                "reschedule it", "yes reschedule",
            }

            rejection_words = {
                "no", "nope", "don't", "do not", "not now",
                "stop", "cancel",
            }

            if normalized in confirmation_words:
                appointment_id = pending.get("appointment_id")
                new_date = pending.get("new_date")
                new_time = pending.get("new_time")

                appointment = get_appointment_by_id(
                    self.db,
                    appointment_id,
                    customer.id,
                )

                if not appointment or appointment.status == "cancelled":
                    self.pending_bookings.pop(customer_phone, None)
                    return {
                        "intent": "RESCHEDULE_APPOINTMENT",
                        "booked": False,
                        "missing": [],
                        "reply": (
                            "I couldn't find an active appointment to "
                            "reschedule."
                        ),
                    }

                # Do not count the appointment being moved as a conflict.
                conflict = (
                    self.db.query(Appointment)
                    .filter(
                        Appointment.appointment_date == new_date,
                        Appointment.appointment_time == new_time,
                        Appointment.status == "confirmed",
                        Appointment.id != appointment.id,
                    )
                    .first()
                )

                if conflict:
                    pending["_awaiting_reschedule_confirmation"] = False
                    pending["new_date"] = new_date
                    pending["new_time"] = new_time
                    self.pending_bookings[customer_phone] = pending
                    return {
                        "intent": "RESCHEDULE_APPOINTMENT",
                        "booked": False,
                        "missing": ["new appointment date/time"],
                        "reply": (
                            "Sorry, that new slot is already booked. "
                            "Please provide another date or time."
                        ),
                    }

                appointment.appointment_date = new_date
                appointment.appointment_time = new_time
                self.db.commit()
                self.db.refresh(appointment)

                # Remove only unsent reminders from the old schedule,
                # then create reminders for the new appointment time.
                self.db.query(Reminder).filter(
                    Reminder.appointment_id == appointment.id,
                    Reminder.status == "pending",
                ).delete(synchronize_session=False)
                self.db.commit()

                create_appointment_reminders(
                    appointment,
                    self.db,
                )

                self.pending_bookings.pop(customer_phone, None)

                return {
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "booked": False,
                    "rescheduled": True,
                    "appointment_id": appointment.id,
                    "missing": [],
                    "reply": (
                        f"✅ Your {appointment.event_type} appointment "
                        f"(ID {appointment.id}) has been rescheduled "
                        f"from {pending.get('old_date')} at "
                        f"{pending.get('old_time')} to "
                        f"{appointment.appointment_date} at "
                        f"{appointment.appointment_time}."
                    ),
                }

            if normalized in rejection_words:
                self.pending_bookings.pop(customer_phone, None)
                return {
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "booked": False,
                    "rescheduled": False,
                    "missing": [],
                    "reply": (
                        "No problem. Your appointment has not been "
                        "rescheduled."
                    ),
                }

            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": (
                    "Please confirm whether you want to reschedule "
                    "the appointment. Reply 'yes' or 'no'."
                ),
            }

        # -------------------------------------------------
        # CONTINUE AN EXISTING RESCHEDULE CONVERSATION
        # -------------------------------------------------

        if pending and pending.get("_conversation_type") == "reschedule":
            appointment_id = pending.get("appointment_id")
            appointment = get_appointment_by_id(
                self.db,
                appointment_id,
                customer.id,
            )

            if not appointment or appointment.status == "cancelled":
                self.pending_bookings.pop(customer_phone, None)
                return {
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "booked": False,
                    "missing": [],
                    "reply": (
                        "I couldn't find that active appointment. "
                        "Please start the reschedule request again."
                    ),
                }

            details = self.extract_booking_details(message)
            new_date = details.get("appointment_date") or pending.get("new_date")
            new_time = details.get("appointment_time") or pending.get("new_time")

            if not new_date:
                pending["new_date"] = None
                self.pending_bookings[customer_phone] = pending
                return {
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "booked": False,
                    "missing": ["new appointment date"],
                    "reply": "What new date would you like for the appointment?",
                }

            if new_date < date.today():
                pending["new_date"] = None
                self.pending_bookings[customer_phone] = pending
                return {
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "booked": False,
                    "missing": ["new appointment date"],
                    "reply": "That date has already passed. Please provide a future date.",
                }

            if not new_time:
                pending["new_date"] = new_date
                pending["new_time"] = None
                self.pending_bookings[customer_phone] = pending
                return {
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "booked": False,
                    "missing": ["new appointment time"],
                    "reply": "What new time would you like for the appointment?",
                }

            pending.update({
                "new_date": new_date,
                "new_time": new_time,
                "_awaiting_reschedule_confirmation": True,
            })
            self.pending_bookings[customer_phone] = pending

            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "appointment_id": appointment.id,
                "missing": [],
                "reply": (
                    f"You want to reschedule appointment ID {appointment.id} "
                    f"from {appointment.appointment_date} at "
                    f"{appointment.appointment_time} to {new_date} at "
                    f"{new_time}. Should I confirm this change? Reply 'yes' or 'no'."
                ),
            }

        # -------------------------------------------------
        # FIND ACTIVE CUSTOMER APPOINTMENTS
        # -------------------------------------------------

        appointments = get_customer_appointments(
            self.db,
            customer.id,
            include_cancelled=False,
        )

        if not appointments:
            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "missing": [],
                "reply": (
                    "You don't have any active appointments that "
                    "can be rescheduled."
                ),
            }

        appointment_id = self.extract_appointment_id(message)
        selected_appointment = None

        if appointment_id:
            selected_appointment = get_appointment_by_id(
                self.db,
                appointment_id,
                customer.id,
            )

            if (
                not selected_appointment
                or selected_appointment.status == "cancelled"
            ):
                return {
                    "intent": "RESCHEDULE_APPOINTMENT",
                    "booked": False,
                    "missing": [],
                    "reply": (
                        f"I couldn't find an active appointment with ID "
                        f"{appointment_id}."
                    ),
                }

        elif len(appointments) == 1:
            selected_appointment = appointments[0]

        else:
            lines = [
                "You have multiple active appointments. Please provide "
                "the Appointment ID you want to reschedule:"
            ]

            for appointment in appointments:
                lines.append(
                    f"\n\n🆔 ID: {appointment.id}"
                    f"\n🎉 Event: {appointment.event_type}"
                    f"\n📅 Date: {appointment.appointment_date}"
                    f"\n⏰ Time: {appointment.appointment_time}"
                )

            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "missing": ["appointment id"],
                "reply": "".join(lines),
            }

        # -------------------------------------------------
        # EXTRACT NEW DATE/TIME FROM THE INITIAL REQUEST
        # -------------------------------------------------

        details = self.extract_booking_details(message)
        new_date = details.get("appointment_date")
        new_time = details.get("appointment_time")

        pending = {
            "_conversation_type": "reschedule",
            "appointment_id": selected_appointment.id,
            "old_date": selected_appointment.appointment_date,
            "old_time": selected_appointment.appointment_time,
            "new_date": new_date,
            "new_time": new_time,
        }

        if not new_date:
            self.pending_bookings[customer_phone] = pending
            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "appointment_id": selected_appointment.id,
                "missing": ["new appointment date"],
                "reply": "What new date would you like for this appointment?",
            }

        if new_date < date.today():
            pending["new_date"] = None
            self.pending_bookings[customer_phone] = pending
            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "appointment_id": selected_appointment.id,
                "missing": ["new appointment date"],
                "reply": "That date has already passed. Please provide a future date.",
            }

        if not new_time:
            self.pending_bookings[customer_phone] = pending
            return {
                "intent": "RESCHEDULE_APPOINTMENT",
                "booked": False,
                "appointment_id": selected_appointment.id,
                "missing": ["new appointment time"],
                "reply": "What new time would you like for this appointment?",
            }

        pending["_awaiting_reschedule_confirmation"] = True
        self.pending_bookings[customer_phone] = pending

        return {
            "intent": "RESCHEDULE_APPOINTMENT",
            "booked": False,
            "appointment_id": selected_appointment.id,
            "missing": [],
            "reply": (
                f"You want to reschedule appointment ID {selected_appointment.id} "
                f"from {selected_appointment.appointment_date} at "
                f"{selected_appointment.appointment_time} to {new_date} at "
                f"{new_time}. Should I confirm this change? Reply 'yes' or 'no'."
            ),
        }

    # =====================================================
    # EXTRACT APPOINTMENT ID
    # =====================================================

    @staticmethod
    def extract_appointment_id(
        message: str,
    ):
        """
        Extract appointment ID from messages such as:

        appointment id 12
        appointment #12
        appointment number 12
        booking id 12
        booking #12
        id 12
        id: 12
        """

        text = message.lower().strip()

        patterns = [
            r"\bappointment\s*(?:id|number|no\.?|#)?\s*[:#-]?\s*(\d+)\b",
            r"\bbooking\s*(?:id|number|no\.?|#)?\s*[:#-]?\s*(\d+)\b",
            r"\bid\s*[:#-]?\s*(\d+)\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
            )

            if match:

                return int(
                    match.group(1)
                )

        return None

    # =====================================================
    # AVAILABILITY HANDLER
    # =====================================================

    def handle_availability(
        self,
        message: str,
        customer_phone: str | None = None,
    ):
        details = self.extract_booking_details(
            message
        )

        # =================================================
        # LOAD PREVIOUS AVAILABILITY DETAILS
        # =================================================

        if (
            customer_phone
            and customer_phone in self.pending_bookings
        ):

            previous = self.pending_bookings[
                customer_phone
            ]

            for key in [
                "appointment_date",
                "appointment_time",
                "event_type",
                "guests",
                "venue",
                "notes",
            ]:

                if (
                    details.get(key) is None
                    and previous.get(key) is not None
                ):

                    details[key] = previous[key]

        appointment_date = details[
            "appointment_date"
        ]

        appointment_time = details[
            "appointment_time"
        ]

        # =================================================
        # DATE MISSING
        # =================================================

        if not appointment_date:

            if customer_phone:

                details["_conversation_type"] = (
                    "availability"
                )

                self.pending_bookings[
                    customer_phone
                ] = details

            return {
                "intent": "CHECK_AVAILABILITY",
                "booked": False,
                "missing": ["appointment date"],
                "reply": (
                    "Sure! What date would you like "
                    "to check?"
                ),
            }

        # =================================================
        # PAST DATE VALIDATION
        # =================================================

        if appointment_date < date.today():

            if customer_phone:

                self.pending_bookings[
                    customer_phone
                ] = {
                    "event_type": details.get(
                        "event_type"
                    ),
                    "appointment_date": None,
                    "appointment_time": details.get(
                        "appointment_time"
                    ),
                    "guests": details.get(
                        "guests"
                    ),
                    "venue": details.get(
                        "venue"
                    ),
                    "notes": details.get(
                        "notes"
                    ),
                    "_conversation_type": "availability",
                }

            return {
                "intent": "CHECK_AVAILABILITY",
                "booked": False,
                "missing": ["appointment date"],
                "reply": (
                    "That date has already passed. "
                    "Please provide a future date."
                ),
            }

        # =================================================
        # TIME MISSING
        # =================================================

        if not appointment_time:

            if customer_phone:

                details["_conversation_type"] = (
                    "availability"
                )

                self.pending_bookings[
                    customer_phone
                ] = details

            return {
                "intent": "CHECK_AVAILABILITY",
                "booked": False,
                "missing": ["appointment time"],
                "reply": (
                    "What time would you like "
                    "to check?"
                ),
            }

        # =================================================
        # CHECK DATABASE
        # =================================================

        available = check_availability(
            self.db,
            appointment_date,
            appointment_time,
        )

        # =================================================
        # AVAILABLE
        # =================================================

        if available:

            if customer_phone:

                self.pending_bookings[
                    customer_phone
                ] = {
                    "event_type": details[
                        "event_type"
                    ],
                    "appointment_date": appointment_date,
                    "appointment_time": appointment_time,
                    "guests": details[
                        "guests"
                    ],
                    "venue": details[
                        "venue"
                    ],
                    "notes": details[
                        "notes"
                    ],
                    "_awaiting_confirmation": True,
                    "_conversation_type": "availability",
                }

            return {
                "intent": "CHECK_AVAILABILITY",
                "booked": False,
                "missing": [],
                "reply": (
                    f"Yes! The slot on "
                    f"{appointment_date} at "
                    f"{appointment_time} is available. "
                    "Would you like me to book it?"
                ),
            }

        # =================================================
        # NOT AVAILABLE
        # =================================================

        if customer_phone:

            self.pending_bookings[
                customer_phone
            ] = {
                "event_type": details[
                    "event_type"
                ],
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "guests": details[
                    "guests"
                ],
                "venue": details[
                    "venue"
                ],
                "notes": details[
                    "notes"
                ],
                "_conversation_type": "availability",
            }

        return {
            "intent": "CHECK_AVAILABILITY",
            "booked": False,
            "missing": [],
            "reply": (
                f"Sorry, the slot on "
                f"{appointment_date} at "
                f"{appointment_time} is already booked. "
                "Please choose another date or time."
            ),
        }

    # =====================================================
    # ASK FOR MISSING FIELD
    # =====================================================

    @staticmethod
    def ask_for_field(field):

        questions = {
            "event type":
                "What type of event would you like to book?",

            "appointment date":
                "Sure! What date would you like to book?",

            "appointment time":
                "What time would you like the event?",

            "number of guests":
                "How many guests will be attending?",

            "venue":
                "Where will the event take place?",
        }

        return questions.get(
            field,
            f"Please provide the {field}.",
        )

    # =====================================================
    # EXTRACT BOOKING DETAILS
    # =====================================================

    def extract_booking_details(
        self,
        message: str,
    ):

        text = message.lower().strip()

        event_type = self.extract_event_type(
            text
        )

        appointment_date = self.extract_date(
            text
        )

        appointment_time = self.extract_time(
            text
        )

        guests = self.extract_guests(
            text
        )

        venue = None

        # =================================================
        # VENUE WITH KEYWORDS
        # =================================================

        venue_match = re.search(
            r"(?:at|venue|location|in)\s+"
            r"([a-zA-Z][a-zA-Z .,-]*?)"
            r"(?=\s+(?:for\s+)?\d+\s*"
            r"(?:people|persons|guests|gests)\b|\s*$)",
            text,
            flags=re.IGNORECASE,
        )

        if venue_match:

            venue = venue_match.group(1).strip()

            venue = re.sub(
                r"^(?:for|at|venue|location|in)\s+",
                "",
                venue,
                flags=re.IGNORECASE,
            ).strip()

            venue = re.sub(
                r"\s+\d{1,2}"
                r"(?::\d{2})?"
                r"\s*(?:am|pm).*$",
                "",
                venue,
                flags=re.IGNORECASE,
            ).strip()

            venue = re.sub(
                r"\s+",
                " ",
                venue,
            ).strip()

        # =================================================
        # STANDALONE VENUE
        # =================================================

        if not venue:

            has_date = (
                self.extract_date(text)
                is not None
            )

            has_time = (
                self.extract_time(text)
                is not None
            )

            has_guests = (
                self.extract_guests(text)
                is not None
            )

            has_event = (
                self.extract_event_type(text)
                is not None
            )

            venue_words = [
                "birthday",
                "wedding",
                "anniversary",
                "meeting",
                "party",
                "conference",
                "engagement",
                "today",
                "tomorrow",
                "people",
                "person",
                "persons",
                "guest",
                "guests",
                "gest",
                "gests",
                "am",
                "pm",
                "available",
                "availability",
                "slot",
                "free",
                "check",
                "yes",
                "okay",
                "ok",
                "no",
                "nope",
            ]

            contains_venue_word = any(
                word in text
                for word in venue_words
            )

            if (
                not has_date
                and not has_time
                and not has_guests
                and not has_event
                and not contains_venue_word
            ):

                venue = text

        return {
            "event_type": event_type,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "guests": guests,
            "venue": venue,
            "notes": None,
        }

    # =====================================================
    # EVENT TYPE
    # =====================================================

    @staticmethod
    def extract_event_type(text: str):

        event_types = [
            "birthday",
            "wedding",
            "anniversary",
            "meeting",
            "party",
            "conference",
            "engagement",
        ]

        for event_type in event_types:

            if event_type in text:

                return event_type

        return None

    # =====================================================
    # DATE EXTRACTION
    # =====================================================

    @staticmethod
    def extract_date(text: str):

        today = date.today()

        # =================================================
        # TODAY
        # =================================================

        if re.search(
            r"\btoday\b",
            text,
        ):

            return today

        # =================================================
        # TOMORROW
        # =================================================

        if re.search(
            r"\btomorrow\b",
            text,
        ):

            return today + timedelta(
                days=1
            )

        # =================================================
        # DD/MM/YYYY
        # DD-MM-YYYY
        # =================================================

        date_match = re.search(
            r"\b(\d{1,2})[/-]"
            r"(\d{1,2})[/-]"
            r"(\d{4})\b",
            text,
        )

        if date_match:

            day = int(
                date_match.group(1)
            )

            month = int(
                date_match.group(2)
            )

            year = int(
                date_match.group(3)
            )

            try:

                return date(
                    year,
                    month,
                    day,
                )

            except ValueError:

                return None

        # =================================================
        # MONTH DD YYYY
        # =================================================

        written_date = re.search(
            r"\b"
            r"(january|february|march|april|may|june|july|"
            r"august|september|october|november|december)"
            r"\s+"
            r"(\d{1,2})(?:st|nd|rd|th)?"
            r"(?:,\s*|\s+)"
            r"(\d{4})"
            r"\b",
            text,
            flags=re.IGNORECASE,
        )

        if written_date:

            month_name = written_date.group(1)

            day = int(
                written_date.group(2)
            )

            year = int(
                written_date.group(3)
            )

            months = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
            }

            try:

                return date(
                    year,
                    months[
                        month_name.lower()
                    ],
                    day,
                )

            except ValueError:

                return None

        # =================================================
        # DD MONTH YYYY
        # =================================================

        reverse_written_date = re.search(
            r"\b"
            r"(\d{1,2})(?:st|nd|rd|th)?"
            r"\s+"
            r"(january|february|march|april|may|june|july|"
            r"august|september|october|november|december)"
            r"\s+"
            r"(\d{4})"
            r"\b",
            text,
            flags=re.IGNORECASE,
        )

        if reverse_written_date:

            day = int(
                reverse_written_date.group(1)
            )

            month_name = (
                reverse_written_date.group(2)
            )

            year = int(
                reverse_written_date.group(3)
            )

            months = {
                "january": 1,
                "february": 2,
                "march": 3,
                "april": 4,
                "may": 5,
                "june": 6,
                "july": 7,
                "august": 8,
                "september": 9,
                "october": 10,
                "november": 11,
                "december": 12,
            }

            try:

                return date(
                    year,
                    months[
                        month_name.lower()
                    ],
                    day,
                )

            except ValueError:

                return None

        return None

    # =====================================================
    # TIME EXTRACTION
    # =====================================================

    @staticmethod
    def extract_time(text: str):

        match = re.search(
            r"\b(\d{1,2})"
            r"(?::(\d{2}))?"
            r"\s*(am|pm)\b",
            text,
            flags=re.IGNORECASE,
        )

        if not match:

            return None

        hour = int(
            match.group(1)
        )

        minute = int(
            match.group(2) or 0
        )

        period = match.group(3).lower()

        # =================================================
        # VALIDATE HOUR
        # =================================================

        if hour < 1 or hour > 12:

            return None

        if minute < 0 or minute > 59:

            return None

        # =================================================
        # CONVERT 12-HOUR FORMAT
        # =================================================

        if period == "pm" and hour != 12:

            hour += 12

        if period == "am" and hour == 12:

            hour = 0

        return datetime.strptime(
            f"{hour}:{minute}",
            "%H:%M",
        ).time()

    # =====================================================
    # GUEST EXTRACTION
    # =====================================================

    @staticmethod
    def extract_guests(text: str):

        text = text.lower().strip()

        # =================================================
        # NUMBER + GUEST WORD
        # =================================================

        match = re.search(
            r"\b(\d+)\s*"
            r"(?:people|person|persons|guest|guests|"
            r"gest|gests)\b",
            text,
            flags=re.IGNORECASE,
        )

        if match:

            guests = int(
                match.group(1)
            )

            if guests > 0:

                return guests

        # =================================================
        # STANDALONE NUMBER
        # =================================================

        standalone = re.fullmatch(
            r"\s*(\d+)\s*",
            text,
        )

        if standalone:

            guests = int(
                standalone.group(1)
            )

            if guests > 0:

                return guests

        return None