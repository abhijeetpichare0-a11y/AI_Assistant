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
        from app.models import (
            Business,
            BusinessHours,
            BusinessRule,
            Service,
            BusinessFAQ,
            BusinessDocument,
        )

        biz = db.query(Business).filter(Business.id == business_id).first()
        biz_name = biz.name if biz and biz.name else "Our business"
        currency = biz.currency if biz and biz.currency else "₹"

        # 1. Operating hours queries
        hours_keywords = ["hours", "timings", "timing", "open", "close", "closed", "schedule", "working hours", "operating hours"]
        if any(kw in q_lower for kw in hours_keywords):
            hours = db.query(BusinessHours).filter(BusinessHours.business_id == business_id).all()
            if hours:
                days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                hours_dict = {h.day.capitalize(): h for h in hours}

                # Check if specific day asked
                for d in days_order:
                    if d.lower() in q_lower:
                        h = hours_dict.get(d)
                        if h:
                            if not h.is_open:
                                return f"{biz_name} is closed on {d}s."
                            return f"On {d}s, {biz_name} is open from {h.opening_time} to {h.closing_time}."

                # Overall hours schedule
                lines = [f"Here are the operating hours for {biz_name}:"]
                for d in days_order:
                    h = hours_dict.get(d)
                    if h:
                        status_str = f"{h.opening_time} - {h.closing_time}" if h.is_open else "Closed"
                        lines.append(f"• {d}: {status_str}")
                return "\n".join(lines)

        # 2. Business Rules & Booking Policies queries
        rule_keywords = [
            "cancellation", "cancel", "cancelling", "reschedule", "rescheduling",
            "deposit", "advance", "late", "delay", "grace period", "notice",
            "group", "guests", "policy", "policies", "rule", "rules", "refund"
        ]
        if any(kw in q_lower for kw in rule_keywords):
            rules = db.query(BusinessRule).filter(BusinessRule.business_id == business_id).all()
            if rules:
                rule_dict = {r.rule_key: r.rule_value for r in rules}

                # Check specific policy queries
                if any(w in q_lower for w in ["cancel", "cancellation", "refund", "notice"]):
                    cancel_rule = rule_dict.get("cancellation_rules")
                    min_notice = rule_dict.get("min_notice_hours")
                    resched_rule = rule_dict.get("rescheduling_rules")
                    if cancel_rule or min_notice:
                        parts = [f"❌ **{biz_name} Cancellation Policy**:"]
                        if cancel_rule:
                            parts.append(cancel_rule)
                        if min_notice:
                            parts.append(f"Notice required: at least {min_notice} hours prior to appointment.")
                        if resched_rule:
                            parts.append(f"Rescheduling: {resched_rule}")
                        return "\n".join(parts)

                if any(w in q_lower for w in ["reschedule", "rescheduling"]):
                    resched_rule = rule_dict.get("rescheduling_rules")
                    if resched_rule:
                        return f"🔄 **{biz_name} Rescheduling Policy**:\n{resched_rule}"

                if any(w in q_lower for w in ["deposit", "advance", "upfront"]):
                    dep_rule = rule_dict.get("deposit_requirements")
                    if dep_rule:
                        return f"💳 **{biz_name} Deposit Policy**:\n{dep_rule}"

                if any(w in q_lower for w in ["late", "delay", "grace"]):
                    late_rule = rule_dict.get("late_arrival_rules")
                    if late_rule:
                        return f"⏰ **{biz_name} Late Arrival Policy**:\n{late_rule}"

                if any(w in q_lower for w in ["group", "guests", "party size"]):
                    group_rule = rule_dict.get("max_group_size")
                    if group_rule:
                        return f"👥 **{biz_name} Group Booking Policy**:\nMaximum group size is {group_rule} guests per appointment."

                # If general policy/rules inquiry
                if any(w in q_lower for w in ["policy", "policies", "rule", "rules"]):
                    lines = [f"📋 **Policies & Guidelines for {biz_name}**:"]
                    if "cancellation_rules" in rule_dict:
                        lines.append(f"• **Cancellation**: {rule_dict['cancellation_rules']}")
                    if "deposit_requirements" in rule_dict:
                        lines.append(f"• **Deposits**: {rule_dict['deposit_requirements']}")
                    if "late_arrival_rules" in rule_dict:
                        lines.append(f"• **Late Arrivals**: {rule_dict['late_arrival_rules']}")
                    if "rescheduling_rules" in rule_dict:
                        lines.append(f"• **Rescheduling**: {rule_dict['rescheduling_rules']}")
                    if len(lines) > 1:
                        return "\n".join(lines)

        # 3. Services Catalog & Pricing queries
        service_keywords = [
            "service", "services", "price", "prices", "pricing", "cost", "how much",
            "rate", "rates", "menu", "catalog", "treatment", "treatments",
            "package", "packages", "what do you offer", "what do you provide", "offerings"
        ]
        if any(kw in q_lower for kw in service_keywords):
            services = db.query(Service).filter(Service.business_id == business_id, Service.is_active == True).all()
            if services:
                # Check for specific service match
                matched_services = [s for s in services if s.name.lower() in q_lower]
                if matched_services:
                    lines = [f"Here is the service information for **{biz_name}**:"]
                    for s in matched_services:
                        desc = f" - {s.description}" if s.description else ""
                        lines.append(f"• **{s.name}**: {currency}{float(s.price):.0f} ({s.duration_minutes} mins){desc}")
                    return "\n".join(lines)

                # General service catalog inquiry
                lines = [f"💇 **Services & Pricing at {biz_name}**:"]
                for s in services:
                    lines.append(f"• **{s.name}** ({s.duration_minutes} mins) - {currency}{float(s.price):.0f}")
                return "\n".join(lines)

        # 4. Business FAQ queries
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

        # 5. Business Documents text fallback with chunk/paragraph relevance scoring
        docs = db.query(BusinessDocument).filter(
            BusinessDocument.business_id == business_id,
            BusinessDocument.processing_status == "processed"
        ).all()
        if docs:
            stopwords = {"what", "when", "where", "which", "your", "have", "with", "this", "that", "from", "they", "will", "would", "about", "there", "their", "does"}
            q_tokens = [w for w in re.findall(r"\b\w{3,}\b", q_lower) if w not in stopwords]
            if q_tokens:
                best_chunk = None
                best_chunk_score = 0

                for doc in docs:
                    doc_text = doc.extracted_text or ""
                    # Split into paragraphs or chunks of 2-3 lines
                    raw_chunks = [p.strip() for p in re.split(r"\n\s*\n", doc_text) if len(p.strip()) > 20]
                    if not raw_chunks:
                        raw_chunks = [line.strip() for line in doc_text.splitlines() if len(line.strip()) > 20]

                    for chunk in raw_chunks:
                        chunk_lower = chunk.lower()
                        chunk_words = set(re.findall(r"\b\w{3,}\b", chunk_lower))
                        overlap = len(set(q_tokens).intersection(chunk_words))
                        # Score chunk based on overlap count
                        if overlap > best_chunk_score and overlap >= 2:
                            best_chunk_score = overlap
                            best_chunk = chunk

                if best_chunk:
                    return best_chunk

        # 6. Business details / Contact info query
        contact_keywords = ["phone", "call", "number", "contact", "location", "address", "where", "about", "who are you"]
        if any(kw in q_lower for kw in contact_keywords) and biz:
            parts = [f"🏢 **{biz.name}**"]
            if biz.description:
                parts.append(biz.description)
            if biz.location:
                parts.append(f"📍 **Location**: {biz.location}")
            if biz.phone:
                parts.append(f"📞 **Phone**: {biz.phone}")
            return "\n".join(parts)

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

            # Tenant-scoped guard:
            # If a business_id is provided, check if business exists.
            # Never fall back to generic "Event AI Assistant" or vector DB when tenant is specified!
            from app.models.business import Business
            biz = db.query(Business).filter(Business.id == business_id).first()
            if biz:
                q_lower = question.lower()
                if any(kw in q_lower for kw in ["what can you do", "what can you help", "what do you do", "how can you help", "help"]):
                    services_hint = f" We offer {biz.services_text}." if biz.services_text else ""
                    return (
                        f"I am the AI assistant for {biz.name}.{services_hint} "
                        f"I can help you with booking appointments, checking service availability & pricing, "
                        f"viewing operating hours, and explaining business policies."
                    )
                return (
                    f"I couldn't find specific information regarding that for {biz.name}. "
                    f"Please feel free to ask about our services, pricing, operating hours, or booking policies."
                )

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