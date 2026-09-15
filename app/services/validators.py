import re

def is_valid_name(text: str | None) -> tuple[bool, str]:
    """
    Validate customer full name:
    - Must be between 2 and 50 characters
    - Must contain alphabetic characters
    - Only allowed: letters, spaces, hyphens, periods
    - Must not be command keywords or single characters
    """
    if not text or not text.strip():
        return False, "Name cannot be empty."

    clean = text.strip()

    if len(clean) < 2:
        return False, "Name must be at least 2 characters long."

    if len(clean) > 50:
        return False, "Name is too long (maximum 50 characters)."

    if not re.search(r"[a-zA-Z]", clean):
        return False, "Name must contain alphabetic letters (e.g. Ram Sharma)."

    if not re.match(r"^[a-zA-Z\s.'-]+$", clean):
        return False, "Name can only contain letters, spaces, hyphens, and periods (e.g. Ram Sharma)."

    bad_keywords = {"book", "slot", "hi", "hello", "hey", "cancel", "reschedule", "yes", "no", "ok", "okay", "help", "menu", "appointment"}
    if clean.lower() in bad_keywords or any(w in bad_keywords for w in clean.lower().split()):
        return False, "Please enter your actual name (e.g. Ram Sharma)."

    return True, ""


def is_valid_phone(text: str | None) -> tuple[bool, str]:
    """
    Validate customer phone number:
    - Must contain between 10 and 15 digits
    - Rejects repetitive dummy digits like 0000000000
    - Checks 10-digit mobile prefix for Indian numbers (6, 7, 8, 9)
    """
    if not text or not text.strip():
        return False, "Phone number cannot be empty."

    digits = re.sub(r"\D", "", text.strip())

    if len(digits) < 10:
        return False, "Phone number must contain at least 10 digits (e.g. 9876543210)."

    if len(digits) > 15:
        return False, "Phone number cannot exceed 15 digits."

    if len(set(digits)) == 1:
        return False, "Please provide a valid active mobile number (cannot be repetitive digits like 0000000000)."

    if len(digits) == 10 and digits[0] not in "6789":
        return False, "Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9 (e.g. 9876543210)."

    return True, ""


def is_valid_email(text: str | None) -> tuple[bool, str]:
    """
    Validate customer email address:
    - Standard RFC 5322 compliant regex: name@domain.tld
    """
    if not text or not text.strip():
        return False, "Email address cannot be empty."

    clean = text.strip()
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_regex, clean):
        return False, "Please enter a valid email address format (e.g. ram@example.com)."

    return True, ""
