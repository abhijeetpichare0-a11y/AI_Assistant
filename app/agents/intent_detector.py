import re


def detect_intent(message: str) -> str:
    """
    Detect user intent supporting English, Hindi, Marathi, and Hinglish.

    Supported Intents:
        - GREETING
        - BUSINESS_INFORMATION
        - BUSINESS_HOURS
        - SERVICE_LIST
        - SERVICE_DETAILS
        - SERVICE_PRICE
        - SERVICE_DURATION
        - STAFF_SEARCH
        - STAFF_DETAILS
        - STAFF_SERVICES
        - CHECK_AVAILABILITY
        - BOOK_APPOINTMENT
        - CONFIRM_BOOKING
        - CANCEL_APPOINTMENT
        - RESCHEDULE_APPOINTMENT
        - MODIFY_APPOINTMENT
        - CUSTOMER_LOOKUP
        - CUSTOMER_HISTORY
        - UPCOMING_APPOINTMENTS
        - APPOINTMENT_DETAILS
        - MULTI_SERVICE_BOOKING
        - GROUP_BOOKING
        - WAITLIST_REQUEST
        - PAYMENT_INFORMATION
        - DEPOSIT_INFORMATION
        - CANCELLATION_POLICY
        - NO_SHOW_POLICY
        - LATE_ARRIVAL
        - FAQ
        - CONTACT_BUSINESS
        - HUMAN_AGENT_REQUEST
        - GOODBYE
        - SWITCH_BUSINESS
        - BUSINESS_ONBOARDING
        - THANK_YOU
        - WHO_ARE_YOU
        - HELP
        - UNKNOWN
    """

    text = (message or "").lower().strip()
    if not text:
        return "UNKNOWN"

    normalized = re.sub(r"[?!.,]+$", "", text).strip()

    # 0. EMERGENCY REQUEST
    if any(re.search(p, normalized) for p in [r"\b(emergency|medical emergency|urgent doctor|ambulance|emergency care|इमर्जन्सी|आणीबाणी)\b"]):
        return "EMERGENCY_REQUEST"

    # 1. SWITCH BUSINESS / ONBOARDING
    if any(re.search(p, normalized) for p in [r"\b(switch|change|reset)\b.*\b(business|category|type|industry)\b", r"🔄 switch business"]):
        return "SWITCH_BUSINESS"

    if any(re.search(p, normalized) for p in [r"\b(register|train|setup|onboard)\b.*\b(business|salon|clinic)\b", r"🏢 register business"]):
        return "BUSINESS_ONBOARDING"

    # 2. CANCELLATION POLICY & REFUND
    cancellation_patterns = [
        r"\b(cancellation policy|cancel policy|reschedule policy|cancellation rule|cancellation terms|refund|refunds|late policy)\b",
        r"रद्दीकरण|रद्द नियम",
    ]
    if any(re.search(p, normalized) for p in cancellation_patterns):
        return "CANCELLATION_POLICY"

    # 3. CANCEL APPOINTMENT ACTION
    cancel_patterns = [
        r"\b(cancel|delete|remove)\b.*\b(appointment|booking|reservation|#\d+|\d+)\b",
        r"\bcancel\s+#?\d+\b",
        r"\b(radd|cancel)\b",
        r"कॅन्सल|रद्द",
        r"❌ cancel booking",
    ]
    if any(re.search(p, normalized) for p in cancel_patterns):
        return "CANCEL_APPOINTMENT"

    # 4. RESCHEDULE / MODIFY APPOINTMENT
    reschedule_patterns = [
        r"\b(reschedule|change|move|modify|update|postpone)\b.*\b(appointment|booking|date|time|slot)\b",
        r"\b(reschedule|move it|change date)\b",
        r"बदला|रिसर्च्युल",
        r"🔄 reschedule booking",
    ]
    if any(re.search(p, normalized) for p in reschedule_patterns):
        return "RESCHEDULE_APPOINTMENT"

    # 5. LATE ARRIVAL POLICY
    late_patterns = [
        r"\b(late|late arrival|delay|running late|15 mins late|15 minutes late)\b",
        r"उशीर|लेट",
    ]
    if any(re.search(p, normalized) for p in late_patterns):
        return "LATE_ARRIVAL"

    # 6. MY APPOINTMENTS / CUSTOMER HISTORY
    my_appts_patterns = [
        r"\b(my|show my|view my|list my|upcoming)\s+(appointment|appointments|booking|bookings)\b",
        r"\bwhat (appointments|bookings) do i have\b",
        r"माझ्या अपॉइंटमेंट|मेरी बुकिंग",
        r"📋 my appointments",
    ]
    if any(re.search(p, normalized) for p in my_appts_patterns):
        return "MY_APPOINTMENTS"

    # 7. BUSINESS HOURS
    hours_patterns = [
        r"\b(hours|opening hours|business hours|open|close|closing time|what time do you open|timing|timings|baje tak open|open hai)\b",
        r"वेळ|टायमिंग|बजे",
    ]
    if any(re.search(p, normalized) for p in hours_patterns):
        return "BUSINESS_HOURS"

    # 8. DEPOSIT INFORMATION
    deposit_patterns = [
        r"\b(deposit|advance|down payment|advance payment|pay a deposit)\b",
        r"अगाऊ रक्कम|डिपॉझिट",
    ]
    if any(re.search(p, normalized) for p in deposit_patterns):
        return "DEPOSIT_INFORMATION"

    # 9. CONTACT BUSINESS
    contact_patterns = [
        r"\b(contact|phone number|phone|email|reach you)\b",
        r"संपर्क|फोन",
    ]
    if any(re.search(p, normalized) for p in contact_patterns):
        return "CONTACT_BUSINESS"

    # 10. SERVICE LIST / CATALOG / OFFERINGS
    service_list_patterns = [
        r"\b(services|service list|packages|treatments|menu|catalog|what services|offerings|what do you offer|which services|all services|view services|show services)\b",
        r"सेवा|सर्व्हिसेस|यादी",
        r"✨ view services & pricing",
    ]
    if any(re.search(p, normalized) for p in service_list_patterns):
        return "SERVICE_LIST"

    # 11. SERVICE DETAILS
    details_patterns = [
        r"\b(service details|treatment details|details about|tell me details|info about|detail|dental cleaning)\b",
    ]
    if any(re.search(p, normalized) for p in details_patterns):
        return "SERVICE_DETAILS"

    # 11. BUSINESS INFORMATION / LOCATION / ABOUT / AMENITIES / FAQ
    info_patterns = [
        r"\b(tell me about|about|located|address|where is|parking|wifi|wi-fi|amenities|walk-ins|walk ins|walk in|accept walk-ins)\b",
        r"माहिती|पत्ता",
    ]
    if any(re.search(p, normalized) for p in info_patterns):
        return "BUSINESS_INFORMATION"

    # 13. SERVICE DURATION
    duration_patterns = [
        r"\b(duration|how long|how much time|time required|take|kitna time|kiti वेळ)\b",
    ]
    if any(re.search(p, normalized) for p in duration_patterns):
        return "SERVICE_DURATION"

    # 14. SERVICE PRICE / COST
    price_patterns = [
        r"\b(price|cost|charge|charges|fee|fees|rate|rates|how much|price kitna|cost kitna)\b",
        r"कीमत|दर|किमत",
    ]
    if any(re.search(p, normalized) for p in price_patterns):
        return "SERVICE_PRICE"

    # 13. STAFF & DOCTOR SEARCH / SERVICES
    staff_patterns = [
        r"\b(rahul|priya|neha|sneha|amit|stylist|therapist|specialist|doctor|physician|dr\.|staff|who works|available staff|what doctors|doctors do you have|who does|who provides|choose my doctor|preferred doctor|child's doctor|child doctor|dermatologist|pediatrician|physiotherapist|physiotherapy)\b",
    ]
    if any(re.search(p, normalized) for p in staff_patterns) and not any(re.search(bp, normalized) for bp in [r"\b(book|appointment|schedule|slot)\b"]):
        return "STAFF_SEARCH"

    # 14. CHECK AVAILABILITY
    availability_patterns = [
        r"\b(available|availability|free slot|open slot|slot|free time|check slot|is there a slot|any slot|slot hai kya|slot आहे का)\b",
        r"\b(today|tomorrow|kal|udya|evening|morning|afternoon|saturday|sunday|monday|tuesday|wednesday|thursday|friday)\b.*\b(slot|time|available)\b",
        r"⏰ check available slots",
    ]
    if any(re.search(p, normalized) for p in availability_patterns):
        return "CHECK_AVAILABILITY"

    # 15. BOOK APPOINTMENT
    booking_patterns = [
        r"\b(book|booking|reserve|reservation|schedule|appointment|book an appointment|make an appointment)\b",
        r"\b(mujhe|i want|i need|book me|book my|book for|karwana hai|करायचे आहे|बुक)\b",
        r"📅 book appointment",
    ]
    if any(re.search(p, normalized) for p in booking_patterns):
        return "BOOK_APPOINTMENT"

    # Check staff patterns if booking didn't trigger
    if any(re.search(p, normalized) for p in staff_patterns):
        return "STAFF_SEARCH"

    # 16. CHITCHAT / CONVERSATIONAL INTENTS
    if any(re.search(p, normalized) for p in [r"^(no|nope|nah|no thanks|not now|nahi|naa)$", r"\b(no thanks|not now)\b"]):
        return "AFFIRMATION_NO"

    if any(re.search(p, normalized) for p in [r"\b(how are you|how are u|how r u|how's it going|how is it going|what's up|whats up|how are you doing|how do you do|wbu)\b"]):
        return "HOW_ARE_YOU"

    if any(re.search(p, normalized) for p in [r"\b(thanks|thank you|thx|thanks a lot|thank you so much|धन्यवाद|शुक्रिया)\b"]):
        return "THANK_YOU"

    if any(re.search(p, normalized) for p in [r"\b(who are you|what's your name|tell me about yourself)\b"]):
        return "WHO_ARE_YOU"

    if any(re.search(p, normalized) for p in [r"\b(bye|goodbye|see you|cya|take care|have a good day|have a nice day|tata)\b"]):
        return "GOODBYE"

    if any(re.search(p, normalized) for p in [r"\b(help|guide me|what can you do)\b"]):
        return "HELP"

    if any(re.search(p, normalized) for p in [r"^(hi|hello|hey|heya|good morning|good afternoon|good evening|namaste|greetings|hi there|hello there|hey there)\b", r"\b(hi|hello|hey|good morning|good afternoon|good evening)\b"]):
        return "GREETING"

    if any(re.search(p, normalized) for p in [r"^(ok|okay|k|kk|sure|got it|alright|all right|cool|great|perfect|awesome|nice|sounds good|yep|yeah|fine|understood|gotcha|roger|sure thing)\b", r"^(ok thanks|okay thanks|cool thanks|great thanks)$"]):
        return "ACKNOWLEDGEMENT"

    return "UNKNOWN"