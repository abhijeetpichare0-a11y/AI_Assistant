import re
from typing import List, Dict, Any, Tuple, Optional
from app.schemas.document_setup import (
    ExtractedServiceItem,
    ExtractedDayHours,
    ExtractedBookingRules,
    ExtractedFAQItem,
    ConflictItem,
    DocumentExtractionResponse
)

DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]

CATEGORY_KEYWORDS = {
    "Salon & Spa": ["salon", "spa", "hair", "nail", "facial", "massage", "barber", "pedicure", "manicure", "waxing", "skin"],
    "Medical Clinic & Healthcare": ["clinic", "hospital", "doctor", "physician", "health", "consultation", "medical", "treatment", "pediatric", "orthopedic"],
    "Dental Clinic": ["dental", "dentist", "teeth", "tooth", "orthodontic", "cleaning", "implant", "cavity", "braces"],
    "Fitness & Gym Studio": ["fitness", "gym", "workout", "trainer", "yoga", "pilates", "crossfit", "exercise", "cardio", "zumba"],
    "Restaurant & Cafe": ["restaurant", "cafe", "menu", "dining", "food", "table", "bar", "kitchen", "dishes", "beverage"],
    "Event Management": ["event", "wedding", "party", "conference", "banquet", "celebration", "catering", "venue"],
    "Consulting & Legal": ["law", "legal", "lawyer", "attorney", "consultant", "advisory", "accounting", "ca", "tax"]
}


def detect_business_category(text: str) -> str:
    lower = text.lower()
    best_cat = "General Services"
    max_matches = 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in lower)
        if matches > max_matches:
            max_matches = matches
            best_cat = cat
    return best_cat


def extract_phone_number(text: str) -> Optional[str]:
    # Match standard Indian/international mobile/landline
    patterns = [
        r"(?:Phone|Call|Contact|Tel|Mobile|WhatsApp)[\s:]*([+]?\d{1,4}[-.\s]?\d{10})",
        r"(?:Phone|Call|Contact|Tel|Mobile|WhatsApp)[\s:]*([+]?\d{1,4}[-.\s]?\d{3,5}[-.\s]?\d{4,6})",
        r"\b(?:[+]91[\-\s]?)?[6-9]\d{9}\b",
        r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1) if m.groups() else m.group(0)
            clean = re.sub(r"[^\d+]", "", raw.strip())
            if len(clean) >= 10:
                return clean
    return None


def extract_email_address(text: str) -> Optional[str]:
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    m = re.search(pattern, text)
    return m.group(0) if m else None


def extract_business_name(text: str, filenames: List[str]) -> Optional[str]:
    # Try explicit prefix
    explicit_patterns = [
        r"(?:Business\s*Name|Name\s*of\s*Business|Company\s*Name|Clinic\s*Name|Salon\s*Name|Studio\s*Name)[\s:]+([^\n\r,]+)",
        r"(?:Welcome\s*to)\s+([^\n\r,.!]+)"
    ]
    for p in explicit_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            if len(cand) > 2 and len(cand) < 60:
                return cand

    # Look at first non-empty lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:5]:
        if line.startswith("---") or line.startswith("[") or "page" in line.lower():
            continue
        # Avoid lines that are just numbers or emails
        if len(line) < 50 and not re.match(r"^[\d\W]+$", line) and not "@" in line:
            return line

    # Fallback to filename
    if filenames:
        base = re.sub(r"[-_]", " ", re.sub(r"\.[^.]+$", "", filenames[0])).title()
        return base

    return None


def extract_location(text: str) -> Optional[str]:
    patterns = [
        r"(?:Address|Location|Situated\s*at|Find\s*us\s*at)[\s:]+([^\n\r]+)",
        r"\b(?:\d+[\w\s,]+(?:Street|Road|Rd|Avenue|Lane|Nagar|Colony|Sector|Plot|Bhavan|Tower|Plaza|Floor|Bengaluru|Bangalore|Mumbai|Delhi|Hyderabad|Chennai|Pune|Kolkata))"
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            cand = m.group(1).strip() if m.groups() else m.group(0).strip()
            if len(cand) > 5 and len(cand) < 150:
                return cand
    return None


def parse_time_str(t_str: str) -> Optional[str]:
    """Convert time strings like 10:00 AM, 10 AM, 10:00, 20:00 to HH:MM in 24h format."""
    clean = t_str.strip().upper()
    # Check 12h format
    m12 = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)", clean)
    if m12:
        hr = int(m12.group(1))
        minute = int(m12.group(2) or 0)
        ampm = m12.group(3)
        if ampm == "PM" and hr < 12:
            hr += 12
        elif ampm == "AM" and hr == 12:
            hr = 0
        return f"{hr:02d}:{minute:02d}"

    # Check 24h format
    m24 = re.search(r"(\d{1,2}):(\d{2})", clean)
    if m24:
        hr = int(m24.group(1))
        minute = int(m24.group(2))
        if 0 <= hr <= 23 and 0 <= minute <= 59:
            return f"{hr:02d}:{minute:02d}"

    return None


def extract_operating_hours(text: str) -> Tuple[List[ExtractedDayHours], bool]:
    """
    Extracts structured hours for Monday to Sunday.
    Returns (list_of_hours, found_explicitly)
    """
    day_map = {day: ExtractedDayHours(day=day, opening_time="10:00", closing_time="20:00", is_open=True) for day in DAYS_OF_WEEK}
    found_explicit = False

    # Check for patterns like:
    # "Monday - Saturday: 10:00 AM - 08:00 PM"
    # "Mon to Fri: 9 AM - 6 PM"
    # "Sunday: Closed"
    patterns = [
        r"(Monday|Mon|Tuesday|Tue|Wednesday|Wed|Thursday|Thu|Friday|Fri|Saturday|Sat|Sunday|Sun)\s*(?:-|to)\s*(Monday|Mon|Tuesday|Tue|Wednesday|Wed|Thursday|Thu|Friday|Fri|Saturday|Sat|Sunday|Sun)[\s:]*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*(?:-|to)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)",
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[\s:]*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*(?:-|to)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)",
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[\s:]*(Closed|Holiday|Off)"
    ]

    day_aliases = {
        "mon": "Monday", "monday": "Monday",
        "tue": "Tuesday", "tuesday": "Tuesday",
        "wed": "Wednesday", "wednesday": "Wednesday",
        "thu": "Thursday", "thursday": "Thursday",
        "fri": "Friday", "friday": "Friday",
        "sat": "Saturday", "saturday": "Saturday",
        "sun": "Sunday", "sunday": "Sunday"
    }

    # Range pattern
    for m in re.finditer(patterns[0], text, re.IGNORECASE):
        d_start_raw = m.group(1).lower()
        d_end_raw = m.group(2).lower()
        start_t = parse_time_str(m.group(3))
        end_t = parse_time_str(m.group(4))

        if d_start_raw in day_aliases and d_end_raw in day_aliases and start_t and end_t:
            found_explicit = True
            s_name = day_aliases[d_start_raw]
            e_name = day_aliases[d_end_raw]
            s_idx = DAYS_OF_WEEK.index(s_name)
            e_idx = DAYS_OF_WEEK.index(e_name)

            if s_idx <= e_idx:
                target_days = DAYS_OF_WEEK[s_idx:e_idx+1]
            else:
                target_days = DAYS_OF_WEEK[s_idx:] + DAYS_OF_WEEK[:e_idx+1]

            for d in target_days:
                day_map[d].opening_time = start_t
                day_map[d].closing_time = end_t
                day_map[d].is_open = True

    # Single day open pattern
    for m in re.finditer(patterns[1], text, re.IGNORECASE):
        d_name_raw = m.group(1).lower()
        start_t = parse_time_str(m.group(2))
        end_t = parse_time_str(m.group(3))
        if d_name_raw in day_aliases and start_t and end_t:
            found_explicit = True
            d = day_aliases[d_name_raw]
            day_map[d].opening_time = start_t
            day_map[d].closing_time = end_t
            day_map[d].is_open = True

    # Closed pattern
    for m in re.finditer(patterns[2], text, re.IGNORECASE):
        d_name_raw = m.group(1).lower()
        if d_name_raw in day_aliases:
            found_explicit = True
            d = day_aliases[d_name_raw]
            day_map[d].is_open = False

    # Check overall "Open 7 Days" or "Everyday: 10 AM - 9 PM"
    everyday_m = re.search(r"(?:Everyday|Daily|All\s*Days|7\s*Days)[\s:]*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*(?:-|to)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)", text, re.IGNORECASE)
    if everyday_m:
        start_t = parse_time_str(everyday_m.group(1))
        end_t = parse_time_str(everyday_m.group(2))
        if start_t and end_t:
            found_explicit = True
            for d in DAYS_OF_WEEK:
                day_map[d].opening_time = start_t
                day_map[d].closing_time = end_t
                day_map[d].is_open = True

    # Default: if Sunday wasn't explicitly set open, keep it closed as common default
    if not found_explicit:
        day_map["Sunday"].is_open = False

    return [day_map[d] for d in DAYS_OF_WEEK], found_explicit


def extract_services_from_text(
    doc_entries: List[Dict[str, Any]]
) -> Tuple[List[ExtractedServiceItem], List[ConflictItem]]:
    """
    Extracts services and prices from document entries.
    Identifies conflicts across documents for identical service names.
    """
    services_found: Dict[str, Dict[str, Any]] = {}
    conflicts: List[ConflictItem] = []

    # Patterns for service extraction
    # 1. Tabular format: Haircut | ₹300 | 30 mins
    # 2. Line format: Haircut - ₹300 - 30 mins
    # 3. Colon format: Haircut: Rs 300 (45 mins)
    service_patterns = [
        # Name | Price | Duration
        r"^\s*([A-Za-z0-9\s&/\-\(\)]{3,40})\s*[\|\,\-]\s*(?:₹|Rs\.?|INR|\$)?\s*(\d+(?:\.\d{2})?)\s*(?:₹|Rs\.?|INR|\$)?\s*[\|\,\-]?\s*(\d+)?\s*(?:min|mins|minutes|hrs|hour)?\s*$",
        # Name: Price
        r"(?:Service|Item)?[\s:]*([A-Za-z0-9\s&/\-\(\)]{3,40})[\s:]+(?:₹|Rs\.?|INR|\$)\s*(\d+(?:\.\d{2})?)"
    ]

    for entry in doc_entries:
        doc_name = entry.get("original_filename", "Document")
        text = entry.get("extracted_text", "")

        for line in text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("---") or line_str.startswith("["):
                continue

            # Strip leading list bullets/numbering: e.g. "1. ", "2) ", "- ", "• "
            clean_line = re.sub(r"^\s*(?:\d+[\.\)]|\-|\*|\•)\s*", "", line_str).strip()
            if not clean_line:
                continue

            # Check table pipes
            if "|" in clean_line:
                parts = [p.strip() for p in clean_line.split("|")]
                if len(parts) >= 2:
                    name_cand = parts[0]
                    # Check if second part or third part is price
                    price_val = None
                    duration_val = 30
                    for part in parts[1:]:
                        # Check price
                        pm = re.search(r"(?:₹|Rs\.?|INR|\$)?\s*(\d+(?:\.\d{2})?)", part)
                        dm = re.search(r"(\d+)\s*(?:min|mins|minute|minutes)", part, re.IGNORECASE)
                        if dm:
                            duration_val = int(dm.group(1))
                        elif pm and price_val is None:
                            try:
                                price_val = float(pm.group(1))
                            except ValueError:
                                pass

                    if price_val is not None and len(name_cand) >= 3 and not name_cand.lower().startswith("service") and not name_cand.lower().startswith("item"):
                        s_name = name_cand.title().strip()
                        record_service(s_name, price_val, duration_val, doc_name, services_found, conflicts)
                        continue

            # Check general lines with price indicator: e.g.
            # "Swedish Full Body Massage: 60 mins - Rs. 2400 (Relaxing therapy)"
            # "Hot Stone Therapy: 50 mins - Rs. 3500"
            # "Deep Tissue Therapy: 45 mins - Rs. 3000"
            price_match = re.search(r"(?:₹|Rs\.?|INR|\$)\s*(\d+(?:\.\d{2})?)", clean_line, re.IGNORECASE)
            if price_match:
                price_str = price_match.group(1)
                try:
                    price_val = float(price_str)
                except ValueError:
                    price_val = None

                if price_val is not None and 10 <= price_val <= 500000:
                    dm = re.search(r"(\d+)\s*(?:min|mins|minute|minutes|hrs|hour|hours)", clean_line, re.IGNORECASE)
                    duration_val = 30
                    if dm:
                        try:
                            d_num = int(dm.group(1))
                            if "hr" in dm.group(0).lower():
                                d_num *= 60
                            duration_val = d_num
                        except ValueError:
                            duration_val = 30

                    first_delim = None
                    for delim in [":", "-", "|"]:
                        idx = clean_line.find(delim)
                        if idx > 2:
                            if first_delim is None or idx < first_delim:
                                first_delim = idx

                    if first_delim:
                        name_cand = clean_line[:first_delim].strip()
                    else:
                        name_cand = clean_line[:price_match.start()].strip()

                    name_cand = re.sub(r"\s*\([^)]*\)", "", name_cand).strip()
                    name_lower = name_cand.lower()

                    skip_words = [
                        "operating hour", "opening hour", "business hour", "timing", "schedule",
                        "cancellation", "deposit", "policy", "policies", "rule", "faq", "question",
                        "contact", "phone", "address", "location", "total", "subtotal", "tax",
                        "service name", "item name", "price list", "menu"
                    ]
                    if (
                        len(name_cand) >= 3 and len(name_cand) <= 60
                        and not any(sw in name_lower for sw in skip_words)
                    ):
                        s_name = name_cand.title()
                        record_service(s_name, price_val, duration_val, doc_name, services_found, conflicts)
                        continue

            # Check regex patterns
            for p in service_patterns:
                m = re.match(p, clean_line, re.IGNORECASE)
                if m:
                    s_name = m.group(1).strip().title()
                    # Skip common headers
                    if s_name.lower() in ["service name", "item name", "price list", "service", "menu", "description"]:
                        continue
                    try:
                        price_val = float(m.group(2))
                    except (ValueError, IndexError):
                        continue

                    duration_val = 30
                    if len(m.groups()) >= 3 and m.group(3):
                        try:
                            duration_val = int(m.group(3))
                        except ValueError:
                            duration_val = 30

                    record_service(s_name, price_val, duration_val, doc_name, services_found, conflicts)
                    break

    result_services = []
    for name, data in services_found.items():
        result_services.append(
            ExtractedServiceItem(
                name=name,
                category=data.get("category", "General"),
                price=data["price"],
                duration_minutes=data["duration_minutes"],
                description=f"Extracted from {data['source']}"
            )
        )

    return result_services, conflicts


def record_service(
    name: str,
    price: float,
    duration: int,
    source: str,
    services_found: Dict[str, Dict[str, Any]],
    conflicts: List[ConflictItem]
):
    key = name.lower()
    if key in services_found:
        existing = services_found[key]
        if abs(existing["price"] - price) > 0.01 and existing["source"] != source:
            conflicts.append(
                ConflictItem(
                    field="price",
                    item_name=name,
                    value1=f"₹{existing['price']:.0f}",
                    source1=existing["source"],
                    value2=f"₹{price:.0f}",
                    source2=source,
                    resolution_suggestion=f"Choose ₹{price:.0f} from {source} or ₹{existing['price']:.0f} from {existing['source']}"
                )
            )
    else:
        services_found[key] = {
            "name": name,
            "price": price,
            "duration_minutes": duration,
            "source": source
        }


def extract_booking_rules_and_faqs(
    text: str
) -> Tuple[ExtractedBookingRules, List[ExtractedFAQItem]]:
    rules = ExtractedBookingRules()
    faqs: List[ExtractedFAQItem] = []

    # Advance notice
    m_notice = re.search(r"(\d+)\s*(?:hours?|hrs?)\s*(?:advance\s*notice|prior\s*notice|before\s*booking)", text, re.IGNORECASE)
    if m_notice:
        try:
            rules.min_notice_hours = int(m_notice.group(1))
        except ValueError:
            pass

    # Cancellation policy
    m_cancel = re.search(r"(?:cancel|cancellation)[\s\w]*?(\d+)\s*(?:hours?|hrs?|days?)", text, re.IGNORECASE)
    if m_cancel:
        rules.cancellation_rules = m_cancel.group(0).strip().capitalize()

    # Buffer minutes
    m_buffer = re.search(r"(\d+)\s*(?:minutes?|mins?)\s*(?:buffer|gap|interval)", text, re.IGNORECASE)
    if m_buffer:
        try:
            rules.booking_buffer_mins = int(m_buffer.group(1))
        except ValueError:
            pass

    # Extract FAQs or Policies
    faq_matches = re.findall(r"(?:Q|Question)[\s:]*([^\n\r]+)[\n\r]+(?:A|Answer)[\s:]*([^\n\r]+)", text, re.IGNORECASE)
    for q, a in faq_matches:
        if len(q.strip()) > 5 and len(a.strip()) > 3:
            faqs.append(ExtractedFAQItem(question=q.strip(), answer=a.strip()))

    # Extract policy bullet points
    policy_patterns = [
        r"(?:Policy|Note|Important|Guidelines?)[\s:]*([^\n\r]+)",
        r"(?:Late\s*arrival|Grace\s*period)[\s:]*([^\n\r]+)",
        r"(?:Payment|Deposit|Refund)[\s:]*([^\n\r]+)"
    ]
    for p in policy_patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            content = m.group(1).strip()
            if len(content) > 10 and not any(f.answer == content for f in faqs):
                title = m.group(0).split(":")[0].strip().title()
                faqs.append(ExtractedFAQItem(question=f"What is the {title} policy?", answer=content))

    return rules, faqs


def extract_business_profile_from_documents(
    doc_entries: List[Dict[str, Any]]
) -> DocumentExtractionResponse:
    """
    Main orchestrator for AI business extraction.
    Combines texts, extracts business details, services, hours, rules, detects conflicts and missing fields.
    """
    combined_text = "\n\n".join(entry.get("extracted_text", "") for entry in doc_entries)
    doc_filenames = [entry.get("original_filename", "Document") for entry in doc_entries]
    doc_ids = [entry.get("id") for entry in doc_entries if entry.get("id")]

    # 1. Business Info
    biz_name = extract_business_name(combined_text, doc_filenames)
    category = detect_business_category(combined_text)
    phone = extract_phone_number(combined_text)
    email = extract_email_address(combined_text)
    location = extract_location(combined_text)

    # 2. Operating Hours
    hours, hours_found = extract_operating_hours(combined_text)

    # 3. Services & Conflicts
    services, conflicts = extract_services_from_text(doc_entries)

    # 4. Booking Rules & FAQs
    rules, faqs = extract_booking_rules_and_faqs(combined_text)

    # 5. Missing Fields Evaluation (Strict No-Fabrication)
    missing_fields = []
    if not biz_name:
        missing_fields.append("Business Name")
    if not phone:
        missing_fields.append("Phone Number")
    if not email:
        missing_fields.append("Email Address")
    if not location:
        missing_fields.append("Physical Address / Location")
    if not services:
        missing_fields.append("Services & Pricing")
    if not hours_found:
        missing_fields.append("Operating Hours (Pre-filled standard 10 AM - 8 PM; please verify)")

    # Description generation from extracted details
    description = f"{biz_name or 'Business'} is a premier {category.lower()} provider"
    if location:
        description += f" located in {location}"
    description += "."

    return DocumentExtractionResponse(
        business_name=biz_name,
        category=category,
        description=description,
        phone=phone,
        email=email,
        location=location,
        currency="INR",
        services=services,
        business_hours=hours,
        booking_rules=rules,
        faqs=faqs,
        missing_fields=missing_fields,
        conflicts=conflicts,
        document_ids=doc_ids,
        document_filenames=doc_filenames
    )
