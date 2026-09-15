import json
import os
import logging
from sqlalchemy.orm import Session
from app.models.business import Business
from app.models.service import Service
from app.models.staff import Staff
from app.models.customer import Customer
from app.models.resource import BusinessResource
from app.models.rule import BusinessRule
from app.models.faq import BusinessFAQ

logging.basicConfig(level=logging.INFO)


def load_business_config(db: Session, config_filepath: str) -> Business:
    if not os.path.exists(config_filepath):
        raise FileNotFoundError(f"Configuration file not found: {config_filepath}")

    with open(config_filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    b_data = data.get("business", {})
    biz_name = b_data.get("name")

    # 1. Create or update Business
    biz = db.query(Business).filter(Business.name == biz_name).first()
    services_text = ", ".join([s["name"] for s in data.get("services", [])])
    if not biz:
        biz = Business(
            name=biz_name,
            category=b_data.get("category", "General"),
            owner_name=b_data.get("owner_name"),
            phone=b_data.get("phone", "+91 0000000000"),
            services_text=services_text,
            description=b_data.get("description"),
            location=b_data.get("location"),
            currency=b_data.get("currency", "INR"),
            operating_hours=b_data.get("operating_hours", "10:00 AM - 08:00 PM"),
            timezone=b_data.get("timezone", "Asia/Kolkata"),
            status="active"
        )
        db.add(biz)
        db.commit()
        db.refresh(biz)
    else:
        biz.category = b_data.get("category", biz.category)
        biz.phone = b_data.get("phone", biz.phone)
        biz.location = b_data.get("location", biz.location)
        biz.currency = b_data.get("currency", biz.currency)
        biz.operating_hours = b_data.get("operating_hours", biz.operating_hours)
        biz.timezone = b_data.get("timezone", biz.timezone)
        biz.description = b_data.get("description", biz.description)
        biz.services_text = services_text
        db.commit()
        db.refresh(biz)

    logging.info(f"Loaded Business '{biz.name}' (ID: {biz.id})")

    # 2. Services
    for s_item in data.get("services", []):
        svc = db.query(Service).filter(Service.business_id == biz.id, Service.name == s_item["name"]).first()
        if not svc:
            svc = Service(
                business_id=biz.id,
                name=s_item["name"],
                category=s_item.get("category"),
                duration_minutes=s_item.get("duration_minutes", 30),
                price=s_item.get("price", 0),
                deposit_percentage=s_item.get("deposit_percentage", 0),
                required_resource_type=s_item.get("required_resource_type"),
                description=s_item.get("description"),
                is_active=True
            )
            db.add(svc)
        else:
            svc.category = s_item.get("category", svc.category)
            svc.duration_minutes = s_item.get("duration_minutes", svc.duration_minutes)
            svc.price = s_item.get("price", svc.price)
            svc.deposit_percentage = s_item.get("deposit_percentage", svc.deposit_percentage)
            svc.required_resource_type = s_item.get("required_resource_type", svc.required_resource_type)
            svc.description = s_item.get("description", svc.description)

    # 3. Staff
    for st_item in data.get("staff", []):
        stf = db.query(Staff).filter(Staff.business_id == biz.id, Staff.name == st_item["name"]).first()
        if not stf:
            stf = Staff(
                business_id=biz.id,
                name=st_item["name"],
                role=st_item.get("role"),
                working_days=st_item.get("working_days"),
                working_start=st_item.get("working_start", "10:00"),
                working_end=st_item.get("working_end", "19:00"),
                break_start=st_item.get("break_start", "14:00"),
                break_end=st_item.get("break_end", "14:30"),
                supported_services=st_item.get("supported_services"),
                is_active=True
            )
            db.add(stf)
        else:
            stf.role = st_item.get("role", stf.role)
            stf.working_days = st_item.get("working_days", stf.working_days)
            stf.working_start = st_item.get("working_start", stf.working_start)
            stf.working_end = st_item.get("working_end", stf.working_end)
            stf.break_start = st_item.get("break_start", stf.break_start)
            stf.break_end = st_item.get("break_end", stf.break_end)
            stf.supported_services = st_item.get("supported_services", stf.supported_services)

    # 4. Resources
    for r_item in data.get("resources", []):
        rsc = db.query(BusinessResource).filter(BusinessResource.business_id == biz.id, BusinessResource.name == r_item["name"]).first()
        if not rsc:
            rsc = BusinessResource(
                business_id=biz.id,
                name=r_item["name"],
                resource_type=r_item.get("resource_type"),
                is_active=True
            )
            db.add(rsc)

    # 5. Rules
    for rule_item in data.get("rules", []):
        rule = db.query(BusinessRule).filter(BusinessRule.business_id == biz.id, BusinessRule.rule_key == rule_item["rule_key"]).first()
        if not rule:
            rule = BusinessRule(
                business_id=biz.id,
                rule_key=rule_item["rule_key"],
                rule_value=str(rule_item["rule_value"]),
                description=rule_item.get("description")
            )
            db.add(rule)
        else:
            rule.rule_value = str(rule_item["rule_value"])

    # 6. FAQs
    for faq_item in data.get("faqs", []):
        faq = db.query(BusinessFAQ).filter(BusinessFAQ.business_id == biz.id, BusinessFAQ.question == faq_item["question"]).first()
        if not faq:
            faq = BusinessFAQ(
                business_id=biz.id,
                question=faq_item["question"],
                answer=faq_item["answer"],
                category=faq_item.get("category", "general")
            )
            db.add(faq)

    db.commit()
    logging.info(f"Successfully seeded database for {biz.name}!")
    return biz


def seed_all_businesses(db: Session):
    base_dir = os.path.join(os.getcwd(), "data", "businesses")
    glowcare_path = os.path.join(base_dir, "glowcare.json")
    test_clinic_path = os.path.join(base_dir, "test_clinic.json")

    if os.path.exists(glowcare_path):
        load_business_config(db, glowcare_path)
    if os.path.exists(test_clinic_path):
        load_business_config(db, test_clinic_path)
