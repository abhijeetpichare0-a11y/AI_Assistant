import os
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.business import Business


def register_business(
    db: Session,
    name: str,
    category: str,
    services_text: str,
    phone: str,
    location: str | None = None,
    owner_name: str | None = None,
    operating_hours: str = "10:00 AM - 08:00 PM",
    timezone: str = "UTC"
) -> Business:
    """
    Registers a new business and self-trains the RAG knowledge base automatically.
    """
    business = Business(
        name=name.strip(),
        category=category.strip(),
        services_text=services_text.strip(),
        phone=phone.strip(),
        location=location.strip() if location else "City Main Branch",
        owner_name=owner_name.strip() if owner_name else "Business Owner",
        operating_hours=operating_hours.strip() if operating_hours else "10:00 AM - 08:00 PM",
        timezone=timezone.strip()
    )
    db.add(business)
    db.commit()
    db.refresh(business)

    # Self-Train RAG Knowledge Base on this business!
    train_rag_on_business(business)

    return business


def get_all_businesses(db: Session) -> list[Business]:
    return db.query(Business).order_by(Business.id.desc()).all()


def train_rag_on_business(business: Business):
    """
    Generates a structured knowledge file for the business and ingests it into RAG.
    """
    try:
        base_dir = Path(__file__).resolve().parents[2]
        kb_dir = base_dir / "app" / "knowledge_base"
        kb_dir.mkdir(parents=True, exist_ok=True)

        filename = f"business_{business.id}.txt"
        file_path = kb_dir / filename

        content = f"""BUSINESS PROFILE: {business.name}
Category: {business.category}
Services Offered: {business.services_text}
Location / Venue: {business.location}
Operating Hours: {business.operating_hours}
Contact Phone: {business.phone}

FREQUENTLY ASKED QUESTIONS FOR {business.name}:

Q: What services are offered at {business.name}?
A: {business.name} offers: {business.services_text}.

Q: Where is {business.name} located?
A: {business.name} is located at {business.location}.

Q: What are the opening hours for {business.name}?
A: {business.name} is open daily from {business.operating_hours}.

Q: How can I book an appointment with {business.name}?
A: You can book an appointment directly through our Event AI Assistant by choosing your preferred date and time.
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[RAG SELF-TRAINING] Successfully generated knowledge base document: {file_path}")

    except Exception as e:
        print(f"[RAG SELF-TRAINING ERROR]: {e}")
