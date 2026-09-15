from pathlib import Path
import re

from app.rag.retriever import Retriever


class RAGAgent:
    """
    RAG Agent for general business-information questions.

    RAG handles informational questions such as:

        - What can you help me with?
        - What services do you provide?
        - What types of events are supported?
        - Can I reschedule an appointment?
        - Can I cancel an appointment?
        - What are the appointment policies?

    Appointment operations such as:

        - booking
        - availability checking
        - cancellation execution
        - rescheduling execution
        - customer appointments

    remain handled by AppointmentAgent and the database.
    """

    def __init__(self):

        base_dir = Path(__file__).resolve().parents[2]

        vector_db_path = (
            base_dir
            / "data"
            / "vector_db"
        )

        self.retriever = Retriever(
            str(vector_db_path)
        )

    def _get_dynamic_business_answer(self, question: str, db, business_id: int) -> str | None:
        if not db or not business_id:
            return None

        q_lower = question.lower()

        # 1. Operating hours queries
        hours_keywords = ["hours", "timings", "timing", "open", "close", "schedule", "working hours", "operating hours"]
        if any(kw in q_lower for kw in hours_keywords):
            from app.models.business_hours import BusinessHours
            from app.models.business import Business
            biz = db.query(Business).filter(Business.id == business_id).first()
            hours = db.query(BusinessHours).filter(BusinessHours.business_id == business_id).all()
            if hours:
                days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                hours_dict = {h.day: h for h in hours}

                # Check if specific day asked
                for d in days_order:
                    if d.lower() in q_lower:
                        h = hours_dict.get(d)
                        if h:
                            biz_name = biz.name if biz else "We"
                            if not h.is_open:
                                return f"{biz_name} is closed on {d}s."
                            return f"On {d}s, {biz_name} is open from {h.opening_time} to {h.closing_time}."

                # Overall hours schedule
                lines = [f"Here are the operating hours for {biz.name if biz else 'our business'}:"]
                for d in days_order:
                    h = hours_dict.get(d)
                    if h:
                        status_str = f"{h.opening_time} - {h.closing_time}" if h.is_open else "Closed"
                        lines.append(f"• {d}: {status_str}")
                return "\n".join(lines)

        # 2. Business FAQ queries
        from app.models.faq import BusinessFAQ
        faqs = db.query(BusinessFAQ).filter(BusinessFAQ.business_id == business_id).all()
        if faqs:
            q_words = set(re.findall(r"\b\w{3,}\b", q_lower))
            best_faq = None
            best_overlap = 0
            for faq in faqs:
                faq_words = set(re.findall(r"\b\w{3,}\b", faq.question.lower()))
                overlap = len(q_words.intersection(faq_words))
                if overlap > best_overlap and overlap >= 2:
                    best_overlap = overlap
                    best_faq = faq
            if best_faq:
                return best_faq.answer

        # 3. Business Documents text fallback
        from app.models.document import BusinessDocument
        docs = db.query(BusinessDocument).filter(
            BusinessDocument.business_id == business_id,
            BusinessDocument.processing_status == "processed"
        ).all()
        if docs:
            q_words = set(re.findall(r"\b\w{4,}\b", q_lower))
            if q_words:
                for doc in docs:
                    doc_text = doc.extracted_text or ""
                    for sentence in doc_text.splitlines():
                        s_lower = sentence.lower()
                        s_words = set(re.findall(r"\b\w{4,}\b", s_lower))
                        if len(q_words.intersection(s_words)) >= 2 and len(sentence.strip()) > 15:
                            return sentence.strip()

        return None

    # =====================================================
    # MAIN ANSWER FUNCTION
    # =====================================================

    def answer(
        self,
        question: str,
        top_k: int = 2,
        db=None,
        business_id: int | None = None
    ) -> str:

        question = (question or "").strip()

        if not question:
            return (
                "Please tell me what information "
                "you would like to know."
            )

        # -------------------------------------------------
        # First check dynamic business FAQ & hours if available
        # -------------------------------------------------
        if db and business_id:
            dynamic_answer = self._get_dynamic_business_answer(question, db, business_id)
            if dynamic_answer:
                return dynamic_answer

        # -------------------------------------------------
        # First try focused answers for known FAQs.
        # -------------------------------------------------

        focused_answer = self._get_focused_answer(
            question
        )

        if focused_answer:
            return focused_answer

        # -------------------------------------------------
        # Otherwise use vector retrieval.
        # -------------------------------------------------

        try:

            results = self.retriever.retrieve(
                question,
                top_k=top_k
            )

        except Exception as e:

            print(
                f"RAG retrieval error: {e}"
            )

            return (
                "I'm sorry, I couldn't retrieve "
                "the requested information right now."
            )

        if not results:

            return (
                "I couldn't find relevant information "
                "about that in my knowledge base."
            )

        # -------------------------------------------------
        # Filter weak retrieval results.
        # -------------------------------------------------

        useful_results = []

        for result in results:

            score = result.get(
                "score",
                0
            )

            text = result.get(
                "text",
                ""
            ).strip()

            if not text:
                continue

            # Because embeddings are normalized and
            # FAISS uses inner-product similarity,
            # scores are generally in the 0-1 range.
            #
            # Keep reasonably relevant results.
            if score >= 0.25:
                useful_results.append(
                    result
                )

        if not useful_results:

            return (
                "I couldn't find relevant information "
                "about that in my knowledge base."
            )

        # -------------------------------------------------
        # Extract useful sections from retrieved documents.
        # -------------------------------------------------

        answers = []

        for result in useful_results:

            extracted = self._extract_relevant_content(
                question,
                result.get("text", "")
            )

            if extracted:
                answers.append(
                    extracted
                )

        # Remove duplicate answers.
        answers = self._remove_duplicates(
            answers
        )

        if not answers:

            return (
                "I found some information, but I couldn't "
                "identify a specific answer to your question."
            )

        # -------------------------------------------------
        # Return concise response.
        # -------------------------------------------------

        return "\n\n".join(
            answers[:2]
        )

    # =====================================================
    # FOCUSED ANSWERS
    # =====================================================

    def _get_focused_answer(
        self,
        question: str
    ) -> str | None:

        text = question.lower().strip()

        # -------------------------------------------------
        # Registered Business Queries (Self-Trained Knowledge)
        # -------------------------------------------------
        try:
            from app.database.database import SessionLocal
            from app.models.business import Business
            db = SessionLocal()
            businesses = db.query(Business).all()
            db.close()

            for b in businesses:
                b_name_lower = b.name.lower()
                b_cat_lower = b.category.lower()
                # Check match on business name or keywords
                name_words = [w for w in b_name_lower.split() if len(w) > 2 and w not in ["and", "the", "for"]]
                is_name_match = b_name_lower in text or any(w in text for w in name_words)

                if is_name_match or b_cat_lower in text:
                    if any(w in text for w in ["service", "services", "offer", "provide", "do"]):
                        return f"**{b.name}** ({b.category}) offers: {b.services}. Located at {b.location}."
                    if any(w in text for w in ["location", "where", "address", "branch"]):
                        return f"**{b.name}** is located at {b.location}. Operating hours: {b.operating_hours}."
                    if any(w in text for w in ["hour", "hours", "open", "time"]):
                        return f"**{b.name}** is open daily from {b.operating_hours}."
                    if any(w in text for w in ["phone", "contact", "call"]):
                        return f"You can reach **{b.name}** at {b.phone}."
                    return f"**{b.name}** ({b.category}) offers {b.services} at {b.location}. Operating hours: {b.operating_hours}."
        except Exception as e:
            print(f"[RAG Business Lookup Notice]: {e}")

        # -------------------------------------------------
        # What can you do?
        # -------------------------------------------------

        if (
            "what can you help" in text
            or "what can you do" in text
            or "what do you do" in text
            or "what does the ai assistant do" in text
        ):
            return (
                "I can help you book appointments, "
                "check availability, cancel appointments, "
                "reschedule appointments, view your "
                "appointments, and provide business "
                "information."
            )

        # -------------------------------------------------
        # Services
        # -------------------------------------------------

        if (
            "what services" in text
            or "services do you provide" in text
            or "what do you provide" in text
            or "your services" in text
        ):
            return (
                "Event AI Assistant provides appointment "
                "and event-management services, including "
                "booking, availability checking, "
                "cancellation, and rescheduling."
            )

        # -------------------------------------------------
        # Event types
        # -------------------------------------------------

        if (
            "what types of events" in text
            or "which events" in text
            or "what events" in text
            or "events do you support" in text
            or "types of events do you support" in text
            or "supported events" in text
        ):
            return (
                "We support several event types, including "
                "party, birthday party, wedding, corporate "
                "event, meeting, anniversary, conference, "
                "and social event."
            )

        # -------------------------------------------------
        # Availability information
        # -------------------------------------------------

        if (
            "manually find available" in text
            or "manually search" in text
            or "find available dates" in text
            or "find available times" in text
        ):
            return (
                "No. The system can automatically check "
                "the database and suggest available dates "
                "and times for you."
            )

        # -------------------------------------------------
        # Can I check availability?
        # -------------------------------------------------

        if (
            "can i check availability" in text
            or "check appointment availability" in text
            or "check availability" in text
        ):
            return (
                "Yes. I can automatically check available "
                "dates and time slots for your appointment."
            )

        # -------------------------------------------------
        # Rescheduling information
        # -------------------------------------------------

        if (
            "can i reschedule" in text
            or "how do i reschedule" in text
            or "reschedule an appointment" in text
        ):
            return (
                "Yes. I can help you reschedule an existing "
                "appointment and find another available "
                "date and time."
            )

        # -------------------------------------------------
        # Cancellation information
        # -------------------------------------------------

        if (
            "can i cancel" in text
            or "how do i cancel" in text
            or "cancel an appointment" in text
        ):
            return (
                "Yes. You can request cancellation through "
                "the AI assistant."
            )

        # -------------------------------------------------
        # Booking policy
        # -------------------------------------------------

        if (
            "booking policy" in text
            or "appointment policy" in text
            or "appointment policies" in text
            or "booking policies" in text
        ):
            return (
                "The system checks appointment availability "
                "before confirming a booking. An appointment "
                "is confirmed only when the requested date "
                "and time are available."
            )

        # -------------------------------------------------
        # WhatsApp & Automated Reminders
        # -------------------------------------------------

        if (
            "whatsapp" in text
            or "reminder" in text
            or "remind" in text
            or "notification" in text
        ):
            return (
                "Yes! Event AI automatically schedules and sends WhatsApp & SMS reminders "
                "to customers at 4 key intervals prior to their appointment: 24 hours, 2 hours, "
                "1 hour, and 10 minutes before the scheduled event time!"
            )

        # -------------------------------------------------
        # Who are you / How are you / Greetings
        # -------------------------------------------------

        if "who are you" in text or "what is your name" in text:
            return (
                "I'm Event AI 🤖, your smart automated event management assistant! "
                "I can help you book appointments, check available slots, manage bookings, "
                "and send automated customer reminders."
            )

        if "how are you" in text or "how's it going" in text:
            return (
                "I'm doing great, thank you for asking! 😊 "
                "I'm here and ready to help you plan your next event. What would you like to do?"
            )

        return None

    # =====================================================
    # CONTENT EXTRACTION
    # =====================================================

    def _extract_relevant_content(
        self,
        question: str,
        document_text: str
    ) -> str:

        text = document_text.strip()

        if not text:
            return ""

        question_lower = question.lower()

        # -------------------------------------------------
        # FAQ document
        # -------------------------------------------------

        if (
            "FREQUENTLY ASKED QUESTIONS"
            in text.upper()
        ):
            return self._extract_faq_answer(
                question_lower,
                text
            )

        # -------------------------------------------------
        # Services document
        # -------------------------------------------------

        if "SERVICES" in text.upper():

            lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ]

            relevant_lines = []

            for line in lines:

                if line.startswith("-"):
                    relevant_lines.append(
                        line
                    )

            if relevant_lines:
                return (
                    "Supported event types:\n"
                    + "\n".join(
                        relevant_lines
                    )
                )

        # -------------------------------------------------
        # Business information
        # -------------------------------------------------

        if "BUSINESS INFORMATION" in text.upper():

            sentences = re.split(
                r"(?<=[.!?])\s+",
                text
            )

            useful = []

            for sentence in sentences:

                sentence = sentence.strip()

                if (
                    sentence
                    and not sentence.upper().startswith(
                        "BUSINESS INFORMATION"
                    )
                ):
                    useful.append(
                        sentence
                    )

            if useful:
                return " ".join(
                    useful[:3]
                )

        # -------------------------------------------------
        # Policies
        # -------------------------------------------------

        if "APPOINTMENT POLICIES" in text.upper():

            lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip()
            ]

            policy_lines = [
                line
                for line in lines
                if not line.upper().startswith(
                    "APPOINTMENT POLICIES"
                )
            ]

            if policy_lines:

                return (
                    "Appointment policies:\n"
                    + "\n".join(
                        f"• {line}"
                        for line in policy_lines
                    )
                )

        # -------------------------------------------------
        # Generic fallback
        # -------------------------------------------------

        sentences = re.split(
            r"(?<=[.!?])\s+",
            text
        )

        keywords = [
            word
            for word in re.findall(
                r"\b[a-zA-Z]{3,}\b",
                question_lower
            )
        ]

        scored_sentences = []

        for sentence in sentences:

            sentence_lower = sentence.lower()

            score = sum(
                1
                for keyword in keywords
                if keyword in sentence_lower
            )

            if score > 0:
                scored_sentences.append(
                    (
                        score,
                        sentence.strip()
                    )
                )

        scored_sentences.sort(
            key=lambda item: item[0],
            reverse=True
        )

        if scored_sentences:

            return " ".join(
                sentence
                for _, sentence
                in scored_sentences[:3]
            )

        return ""

    # =====================================================
    # FAQ EXTRACTION
    # =====================================================

    def _extract_faq_answer(
        self,
        question: str,
        document_text: str
    ) -> str:

        blocks = re.split(
            r"\n\s*\n",
            document_text
        )

        best_block = None
        best_score = 0

        question_words = set(
            re.findall(
                r"\b[a-zA-Z]{3,}\b",
                question
            )
        )

        for block in blocks:

            block_lower = block.lower()

            if not block_lower.startswith("q:"):
                continue

            block_words = set(
                re.findall(
                    r"\b[a-zA-Z]{3,}\b",
                    block_lower
                )
            )

            score = len(
                question_words.intersection(
                    block_words
                )
            )

            if score > best_score:
                best_score = score
                best_block = block

        if best_block:

            answer_match = re.search(
                r"A:\s*(.*)",
                best_block,
                flags=re.IGNORECASE | re.DOTALL
            )

            if answer_match:

                answer = (
                    answer_match.group(1)
                    .strip()
                )

                if answer:
                    return answer

        return ""

    # =====================================================
    # DUPLICATE REMOVAL
    # =====================================================

    def _remove_duplicates(
        self,
        answers: list[str]
    ) -> list[str]:

        unique = []
        seen = set()

        for answer in answers:

            normalized = " ".join(
                answer.lower().split()
            )

            if normalized in seen:
                continue

            seen.add(normalized)
            unique.append(answer)

        return unique