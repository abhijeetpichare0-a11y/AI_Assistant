import logging
from typing import List, Dict, Any, Union
from sqlalchemy.orm import Session

from app.models import (
    Business,
    Service,
    BusinessHours,
    BusinessRule,
    BusinessFAQ,
    BusinessDocument
)
from app.services.ai_business_extractor import extract_business_profile_from_documents

logger = logging.getLogger(__name__)


def sync_document_data_to_system(
    db: Session,
    business_id: int,
    documents: List[Union[BusinessDocument, Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Extracts business profile, services, weekly operating hours, rules,
    and FAQs from uploaded documents and syncs them into the database
    for the specified business.
    """
    if not business_id or not documents:
        return {
            "services_added": 0,
            "services_updated": 0,
            "hours_updated": 0,
            "rules_updated": 0,
            "faqs_added": 0,
            "business_updated": False,
            "details": {}
        }

    # Fetch business
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        logger.warning(f"Cannot sync documents: Business ID {business_id} not found.")
        return {
            "services_added": 0,
            "services_updated": 0,
            "hours_updated": 0,
            "rules_updated": 0,
            "faqs_added": 0,
            "business_updated": False,
            "details": {"error": f"Business ID {business_id} not found."}
        }

    # Prepare document input entries for ai_business_extractor
    doc_entries = []
    for d in documents:
        if isinstance(d, dict):
            fname = d.get("original_filename") or "document"
            text = d.get("extracted_text") or ""
        else:
            fname = getattr(d, "original_filename", "document")
            text = getattr(d, "extracted_text", "") or ""

        if text.strip():
            doc_entries.append({
                "original_filename": fname,
                "extracted_text": text
            })

    if not doc_entries:
        return {
            "services_added": 0,
            "services_updated": 0,
            "hours_updated": 0,
            "rules_updated": 0,
            "faqs_added": 0,
            "business_updated": False,
            "details": {"message": "No non-empty text found in documents."}
        }

    # Extract structured business profile using AI/heuristic extractor
    extraction = extract_business_profile_from_documents(doc_entries)

    services_added = 0
    services_updated = 0
    synced_service_names = []

    # 1. Sync Services
    if extraction.services:
        for s in extraction.services:
            s_name = (s.name or "").strip()
            if not s_name:
                continue

            existing_svc = db.query(Service).filter(
                Service.business_id == business_id,
                Service.name.ilike(s_name)
            ).first()

            s_price = float(s.price) if s.price is not None else 0.0
            s_dur = int(s.duration_minutes) if s.duration_minutes is not None and s.duration_minutes > 0 else 30
            s_cat = (s.category or "General").strip()
            s_desc = (s.description or "").strip()

            if not existing_svc:
                new_svc = Service(
                    business_id=business_id,
                    name=s_name,
                    category=s_cat,
                    price=s_price,
                    duration_minutes=s_dur,
                    description=s_desc,
                    is_active=True
                )
                db.add(new_svc)
                services_added += 1
                synced_service_names.append(f"{s_name} (added)")
            else:
                updated = False
                if s_price > 0 and existing_svc.price != s_price:
                    existing_svc.price = s_price
                    updated = True
                if s_dur > 0 and existing_svc.duration_minutes != s_dur:
                    existing_svc.duration_minutes = s_dur
                    updated = True
                if s_desc and not existing_svc.description:
                    existing_svc.description = s_desc
                    updated = True
                if updated:
                    services_updated += 1
                    synced_service_names.append(f"{s_name} (updated)")

        db.commit()

        # Update Business.services_text cache
        all_active_services = db.query(Service).filter(
            Service.business_id == business_id,
            Service.is_active == True
        ).all()
        if all_active_services:
            biz.services_text = ", ".join(svc.name for svc in all_active_services)
            db.commit()

    # 2. Sync Weekly Operating Hours
    hours_updated = 0
    hours_summary = []
    if extraction.business_hours:
        for h in extraction.business_hours:
            if not h.day:
                continue
            existing_hour = db.query(BusinessHours).filter(
                BusinessHours.business_id == business_id,
                BusinessHours.day.ilike(h.day.strip())
            ).first()

            if existing_hour:
                existing_hour.opening_time = h.opening_time or "10:00"
                existing_hour.closing_time = h.closing_time or "20:00"
                existing_hour.is_open = bool(h.is_open)
                hours_updated += 1
                status = f"{existing_hour.opening_time}-{existing_hour.closing_time}" if existing_hour.is_open else "Closed"
                hours_summary.append(f"{h.day}: {status}")
            else:
                new_hour = BusinessHours(
                    business_id=business_id,
                    day=h.day.capitalize(),
                    opening_time=h.opening_time or "10:00",
                    closing_time=h.closing_time or "20:00",
                    is_open=bool(h.is_open)
                )
                db.add(new_hour)
                hours_updated += 1
                status = f"{new_hour.opening_time}-{new_hour.closing_time}" if new_hour.is_open else "Closed"
                hours_summary.append(f"{h.day}: {status}")
        db.commit()

    # 3. Sync Booking Rules & Policies
    rules_updated = 0
    rules_summary = []
    if extraction.booking_rules:
        rule_map = {
            "cancellation_rules": extraction.booking_rules.cancellation_rules,
            "rescheduling_rules": extraction.booking_rules.rescheduling_rules,
            "deposit_requirements": extraction.booking_rules.deposit_requirements,
            "late_arrival_rules": extraction.booking_rules.late_arrival_rules,
            "min_notice_hours": str(extraction.booking_rules.min_notice_hours) if extraction.booking_rules.min_notice_hours is not None else None,
            "max_advance_days": str(extraction.booking_rules.max_advance_days) if extraction.booking_rules.max_advance_days is not None else None,
            "booking_buffer_mins": str(extraction.booking_rules.booking_buffer_mins) if extraction.booking_rules.booking_buffer_mins is not None else None,
            "max_group_size": str(extraction.booking_rules.max_group_size) if extraction.booking_rules.max_group_size is not None else None,
        }
        for r_key, r_val in rule_map.items():
            if r_val is not None and str(r_val).strip() and str(r_val).strip() != "None":
                val_str = str(r_val).strip()
                rule_record = db.query(BusinessRule).filter(
                    BusinessRule.business_id == business_id,
                    BusinessRule.rule_key == r_key
                ).first()
                if not rule_record:
                    db.add(BusinessRule(business_id=business_id, rule_key=r_key, rule_value=val_str))
                    rules_updated += 1
                    rules_summary.append(f"{r_key}: {val_str}")
                else:
                    if rule_record.rule_value != val_str:
                        rule_record.rule_value = val_str
                        rules_updated += 1
                        rules_summary.append(f"{r_key}: {val_str}")
        db.commit()

    # 4. Sync FAQs
    faqs_added = 0
    faqs_summary = []
    if extraction.faqs:
        for faq in extraction.faqs:
            q_text = (faq.question or "").strip()
            a_text = (faq.answer or "").strip()
            if not q_text or not a_text:
                continue

            existing_faq = db.query(BusinessFAQ).filter(
                BusinessFAQ.business_id == business_id,
                BusinessFAQ.question.ilike(q_text)
            ).first()

            if not existing_faq:
                db.add(BusinessFAQ(
                    business_id=business_id,
                    question=q_text,
                    answer=a_text
                ))
                faqs_added += 1
                faqs_summary.append(q_text)
            else:
                if existing_faq.answer != a_text:
                    existing_faq.answer = a_text
                    faqs_added += 1
                    faqs_summary.append(f"{q_text} (updated)")
        db.commit()

    # 5. Sync Business Profile attributes if generic/missing
    business_updated = False
    if extraction.business_name and biz.name in ["My Business", "Default Business", "", None]:
        biz.name = extraction.business_name
        business_updated = True

    if extraction.category and (biz.category in ["General", "General Services", "", None] or not biz.category):
        biz.category = extraction.category
        business_updated = True

    if extraction.phone and (not biz.phone or biz.phone in ["+1-000-000-0000", "+91-0000000000"]):
        biz.phone = extraction.phone
        business_updated = True

    if extraction.location and not biz.location:
        biz.location = extraction.location
        business_updated = True

    if extraction.description and (not biz.description or len(biz.description) < len(extraction.description)):
        biz.description = extraction.description
        business_updated = True

    if business_updated:
        db.commit()

    return {
        "services_added": services_added,
        "services_updated": services_updated,
        "services_total": db.query(Service).filter(Service.business_id == business_id, Service.is_active == True).count(),
        "hours_updated": hours_updated,
        "rules_updated": rules_updated,
        "faqs_added": faqs_added,
        "business_updated": business_updated,
        "details": {
            "services": synced_service_names,
            "hours": hours_summary,
            "rules": rules_summary,
            "faqs": faqs_summary,
            "conflicts": [f"{c.item_name}: {c.field} discrepancy" for c in extraction.conflicts] if extraction.conflicts else []
        }
    }
