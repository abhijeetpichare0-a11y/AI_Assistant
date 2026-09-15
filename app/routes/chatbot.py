from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.appointment_agent import AppointmentAgent
from app.agents.rag_agent import RAGAgent
from app.database.database import get_db


router = APIRouter(
    prefix="/chat",
    tags=["AI Chatbot"]
)


# =========================================================
# REQUEST / RESPONSE MODELS
# =========================================================

class ChatRequest(BaseModel):
    business_id: int | None = None
    message: str
    customer_phone: str | None = None
    customer_name: str | None = None
    customer_email: str | None = None


from typing import Any

class ChatResponse(BaseModel):
    intent: str
    booked: bool
    reply: str
    appointment_id: int | None = None
    pdf_url: str | None = None
    missing: list[str] | None = None
    cancelled: bool | None = None
    rescheduled: bool | None = None
    appointments: list[dict] | None = None
    options: list[Any] | None = None
    next_step: str | None = None


# =========================================================
# RAG AGENT
# =========================================================

rag_agent = None


def get_rag_agent():
    """
    Create the RAG agent only when it is actually needed.

    This avoids loading the embedding model every time
    the chatbot receives a message.
    """
    global rag_agent

    if rag_agent is None:
        rag_agent = RAGAgent()

    return rag_agent


# =========================================================
# RAG ROUTING HELPERS
# =========================================================

def should_use_rag(message: str, result: dict) -> bool:
    """
    Decide whether a GENERAL_QUERY should be handled by RAG.

    IMPORTANT:
    Appointment conversation messages must NOT be sent to RAG.

    Examples that should NOT go to RAG:
        yes
        no
        ok
        50
        300
        2026-09-08
        3 PM
        Latur
        conference

    Examples that SHOULD go to RAG:
        What services do you provide?
        What types of events do you support?
        What can you help me with?
        Can I cancel an appointment?
        Do you support weddings?
        What are your appointment policies?
    """

    message = (message or "").strip().lower()

    if not message:
        return False

    # -----------------------------------------------------
    # 1. Never send active appointment-flow responses to RAG
    # -----------------------------------------------------

    if result.get("missing"):
        return False

    if result.get("options"):
        return False

    if result.get("next_step"):
        return False

    # -----------------------------------------------------
    # 2. Never send appointment-operation results to RAG
    # -----------------------------------------------------

    appointment_intents = {
        "BOOK_APPOINTMENT",
        "CHECK_AVAILABILITY",
        "CANCEL_APPOINTMENT",
        "RESCHEDULE_APPOINTMENT",
        "MY_APPOINTMENTS",
    }

    if result.get("intent") in appointment_intents:
        return False

    # -----------------------------------------------------
    # 3. Short confirmations / acknowledgements
    # -----------------------------------------------------

    simple_responses = {
        "yes",
        "yeah",
        "yep",
        "yup",
        "sure",
        "ok",
        "okay",
        "fine",
        "alright",
        "all right",
        "no",
        "nope",
        "thanks",
        "thank you",
        "thx",
        "great",
        "good",
        "done",
    }

    if message in simple_responses:
        return False

    # -----------------------------------------------------
    # 4. Numeric-only messages
    # -----------------------------------------------------

    if message.isdigit():
        return False

    # -----------------------------------------------------
    # 5. Date-like messages
    # -----------------------------------------------------

    date_patterns = [
        r"^\d{4}-\d{1,2}-\d{1,2}$",
        r"^\d{1,2}/\d{1,2}/\d{4}$",
        r"^\d{1,2}-\d{1,2}-\d{4}$",
        r"^\d{1,2}:\d{2}$",
        r"^\d{1,2}:\d{2}\s*(am|pm)$",
        r"^\d{1,2}\s*(am|pm)$",
    ]

    import re

    for pattern in date_patterns:
        if re.fullmatch(pattern, message):
            return False

    # -----------------------------------------------------
    # 6. Common appointment conversation answers
    # -----------------------------------------------------

    appointment_answers = {
        "today",
        "tomorrow",
        "morning",
        "afternoon",
        "evening",
        "night",
        "party",
        "birthday",
        "birthday party",
        "wedding",
        "meeting",
        "conference",
        "anniversary",
        "engagement",
        "social event",
    }

    if message in appointment_answers:
        return False

    # -----------------------------------------------------
    # 7. Venue/location-style short answers
    # -----------------------------------------------------

    # If the message is a single short word and does not
    # look like a question, don't send it to RAG.
    words = message.split()

    if len(words) <= 2:
        question_words = {
            "what",
            "which",
            "who",
            "where",
            "when",
            "why",
            "how",
            "can",
            "do",
            "does",
            "is",
            "are",
            "will",
            "tell",
        }

        if not any(word in question_words for word in words):
            information_keywords = {
                "service",
                "services",
                "event",
                "events",
                "policy",
                "policies",
                "business",
                "assistant",
                "support",
                "appointment",
                "booking",
            }

            if not any(
                keyword in message
                for keyword in information_keywords
            ):
                return False

    # -----------------------------------------------------
    # 8. Strong information/question indicators
    # -----------------------------------------------------

    question_words = [
        "what",
        "which",
        "who",
        "where",
        "when",
        "why",
        "how",
        "can you",
        "can i",
        "do you",
        "does the",
        "is there",
        "tell me",
        "explain",
        "information",
    ]

    information_keywords = [
        "service",
        "services",
        "event types",
        "types of events",
        "support",
        "supported",
        "business information",
        "about your business",
        "appointment policy",
        "appointment policies",
        "policy",
        "policies",
        "faq",
        "frequently asked",
        "what can you do",
        "what do you do",
        "what do you provide",
        "what events",
    ]

    if any(
        phrase in message
        for phrase in question_words
    ):
        return True

    if any(
        phrase in message
        for phrase in information_keywords
    ):
        return True

    # -----------------------------------------------------
    # 9. Otherwise, don't use RAG
    # -----------------------------------------------------

    return False


# =========================================================
# CHAT ENDPOINT
# =========================================================

@router.post(
    "/",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):

    message = (request.message or "").strip()

    # -----------------------------------------------------
    # Empty message
    # -----------------------------------------------------

    if not message:
        return ChatResponse(
            intent="GENERAL_QUERY",
            booked=False,
            reply="Please tell me how I can help you.",
            appointment_id=None,
            missing=None,
            cancelled=None,
            rescheduled=None,
            appointments=None,
            options=None,
            next_step=None
        )

    # -----------------------------------------------------
    # Appointment Agent ALWAYS runs first
    # -----------------------------------------------------

    agent = AppointmentAgent(db)

    result = agent.process(
        message=message,
        customer_phone=request.customer_phone,
        customer_name=request.customer_name,
        customer_email=request.customer_email,
        business_id=request.business_id
    )

    # -----------------------------------------------------
    # Make response fields safe
    # -----------------------------------------------------

    result.setdefault("intent", "GENERAL_QUERY")
    result.setdefault("booked", False)
    result.setdefault("reply", "")
    result.setdefault("appointment_id", None)
    result.setdefault("pdf_url", None)
    result.setdefault("missing", None)
    result.setdefault("cancelled", None)
    result.setdefault("rescheduled", None)
    result.setdefault("appointments", None)
    result.setdefault("options", None)
    result.setdefault("next_step", None)

    # -----------------------------------------------------
    # RAG ONLY for genuine information queries
    # -----------------------------------------------------

    if (
        result.get("intent") == "GENERAL_QUERY"
        and should_use_rag(message, result)
    ):
        try:
            rag = get_rag_agent()

            rag_reply = rag.answer(
                question=message,
                top_k=2,
                db=db,
                business_id=request.business_id
            )

            if rag_reply:
                result["reply"] = rag_reply

        except Exception as e:
            print(
                f"RAG integration error: {e}"
            )

    # -----------------------------------------------------
    # Ensure contextual options with 'Other (Type your own)'
    # -----------------------------------------------------

    from datetime import datetime, timedelta

    missing = result.get("missing") or []
    next_step = result.get("next_step")
    phone_key = request.customer_phone or "anonymous"
    active_biz = agent.pending_bookings.get(phone_key, {}).get("active_business_type")

    raw_options = result.get("options")
    if raw_options is not None and isinstance(raw_options, list):
        sanitized = []
        for opt in raw_options:
            if isinstance(opt, (str, dict)):
                sanitized.append(opt)
            else:
                sanitized.append(str(opt))

        has_other = any(
            (isinstance(o, str) and "other" in o.lower()) or
            (isinstance(o, dict) and "other" in str(o.get("label", "")).lower())
            for o in sanitized
        )
        if sanitized and not has_other:
            sanitized.append("💬 Other (Type your own)")
        result["options"] = sanitized
    else:
        if "event type" in missing or next_step == "event_type":
            result["options"] = agent.get_options_for_field("event type", active_biz=active_biz)
        elif "appointment date" in missing or next_step == "appointment_date":
            today = datetime.now()
            opts = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 6)]
            opts.append("💬 Other (Type your own)")
            result["options"] = opts
        elif "appointment time" in missing or next_step == "appointment_time":
            result["options"] = ["10:00 AM", "01:00 PM", "04:00 PM", "06:00 PM", "08:00 PM", "💬 Other (Type your own)"]
        elif "number of guests" in missing or next_step == "guests":
            result["options"] = agent.get_options_for_field("number of guests", active_biz=active_biz)
        elif "venue" in missing or next_step == "venue":
            result["options"] = agent.get_options_for_field("venue", active_biz=active_biz)
        else:
            result["options"] = agent.get_default_options_for_business(active_biz)

    return result