import os
import sys
import io
import unittest
from datetime import datetime
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database.database import SessionLocal, engine, Base
from app.models.user import User
from app.models.business import Business
from app.models.document import BusinessDocument
from app.services.document_parser import (
    parse_and_save_uploaded_file,
    sanitize_filename,
    extract_text_from_txt,
    extract_text_from_csv
)
from fastapi import HTTPException


class TestOwnerDocumentUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)
        cls.db = SessionLocal()

        # Create Business 1 and Owner 1
        cls.biz1 = cls.db.query(Business).filter(Business.name == "DocTest Spa A").first()
        if not cls.biz1:
            cls.biz1 = Business(
                name="DocTest Spa A",
                category="Salon & Spa",
                owner_name="Owner One",
                phone="9100000001",
                services_text="Massage, Facial",
                description="Test Spa A",
                location="Location A",
                currency="INR",
                timezone="Asia/Kolkata"
            )
            cls.db.add(cls.biz1)
            cls.db.commit()
            cls.db.refresh(cls.biz1)

        cls.owner1 = cls.db.query(User).filter(User.phone == "9100000001").first()
        if not cls.owner1:
            cls.owner1 = User(
                username="Owner One",
                phone="9100000001",
                role="owner",
                business_id=cls.biz1.id
            )
            cls.db.add(cls.owner1)
            cls.db.commit()
            cls.db.refresh(cls.owner1)

        # Create Business 2 and Owner 2 (for tenant isolation testing)
        cls.biz2 = cls.db.query(Business).filter(Business.name == "DocTest Salon B").first()
        if not cls.biz2:
            cls.biz2 = Business(
                name="DocTest Salon B",
                category="Salon & Spa",
                owner_name="Owner Two",
                phone="9100000002",
                services_text="Haircut, Styling",
                description="Test Salon B",
                location="Location B",
                currency="INR",
                timezone="Asia/Kolkata"
            )
            cls.db.add(cls.biz2)
            cls.db.commit()
            cls.db.refresh(cls.biz2)

        cls.owner2 = cls.db.query(User).filter(User.phone == "9100000002").first()
        if not cls.owner2:
            cls.owner2 = User(
                username="Owner Two",
                phone="9100000002",
                role="owner",
                business_id=cls.biz2.id
            )
            cls.db.add(cls.owner2)
            cls.db.commit()
            cls.db.refresh(cls.owner2)

        cls.headers_owner1 = {
            "X-User-Phone": cls.owner1.phone,
            "X-User-Role": "owner"
        }
        cls.headers_owner2 = {
            "X-User-Phone": cls.owner2.phone,
            "X-User-Role": "owner"
        }

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_sanitize_filename(self):
        filename = "../../malicious/path/to/my file (1).txt"
        sanitized = sanitize_filename(filename)
        self.assertNotIn("..", sanitized)
        self.assertNotIn("/", sanitized)
        self.assertNotIn("\\", sanitized)
        self.assertTrue(sanitized.endswith(".txt"))

    def test_02_parse_and_save_txt(self):
        content = b"Welcome to Zenith Spa. We offer Swedish Massage for 1500 INR."
        parsed = parse_and_save_uploaded_file(
            file_bytes=content,
            original_filename="services_menu.txt",
            owner_id=self.owner1.id,
            business_id=self.biz1.id
        )
        self.assertEqual(parsed["processing_status"], "processed")
        self.assertEqual(parsed["file_type"], "txt")
        self.assertIn("Swedish Massage", parsed["extracted_text"])
        self.assertTrue(os.path.exists(parsed["file_path"]))
        # Cleanup file
        if os.path.exists(parsed["file_path"]):
            os.remove(parsed["file_path"])

    def test_03_parse_and_save_csv(self):
        csv_bytes = b"Service,Price,Duration\nFacial Glow,1200,45\nPedicure,800,30\n"
        parsed = parse_and_save_uploaded_file(
            file_bytes=csv_bytes,
            original_filename="price_list.csv",
            owner_id=self.owner1.id,
            business_id=self.biz1.id
        )
        self.assertEqual(parsed["processing_status"], "processed")
        self.assertIn("Facial Glow", parsed["extracted_text"])
        self.assertIn("1200", parsed["extracted_text"])
        if os.path.exists(parsed["file_path"]):
            os.remove(parsed["file_path"])

    def test_04_reject_empty_file(self):
        with self.assertRaises(HTTPException) as ctx:
            parse_and_save_uploaded_file(
                file_bytes=b"",
                original_filename="empty.txt",
                owner_id=self.owner1.id
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("empty", ctx.exception.detail.lower())

    def test_05_reject_unsupported_format(self):
        with self.assertRaises(HTTPException) as ctx:
            parse_and_save_uploaded_file(
                file_bytes=b"dangerous executable bytes",
                original_filename="script.exe",
                owner_id=self.owner1.id
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("unsupported file format", ctx.exception.detail.lower())

    def test_06_api_upload_single_document(self):
        file_payload = [
            ("files", ("catalog_pricing.txt", io.BytesIO(b"Hair Spa: 1500 INR\nBeard Styling: 500 INR"), "text/plain"))
        ]
        res = self.client.post("/owner/documents", files=file_payload, headers=self.headers_owner1)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertIn("documents", data)
        self.assertEqual(len(data["documents"]), 1)
        doc = data["documents"][0]
        self.assertEqual(doc["original_filename"], "catalog_pricing.txt")
        self.assertEqual(doc["processing_status"], "processed")
        self.assertIn("Hair Spa", doc["extracted_text_preview"])

    def test_07_api_upload_multiple_documents(self):
        files_payload = [
            ("files", ("menu_food.txt", io.BytesIO(b"Coffee: 150 INR\nCroissant: 200 INR"), "text/plain")),
            ("files", ("hours.csv", io.BytesIO(b"Day,Hours\nMon,9-18\nTue,9-18"), "text/csv"))
        ]
        res = self.client.post("/owner/documents", files=files_payload, headers=self.headers_owner1)
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(len(data["documents"]), 2)

    def test_08_api_list_owner_documents(self):
        res = self.client.get("/owner/documents", headers=self.headers_owner1)
        self.assertEqual(res.status_code, 200)
        docs = res.json()
        self.assertTrue(len(docs) >= 3)
        self.assertTrue(all("extracted_text_preview" in d for d in docs))
        self.assertTrue(all("processing_status" in d for d in docs))

    def test_09_api_get_document_detail_and_multi_tenant_isolation(self):
        # List documents for Owner 1
        res1 = self.client.get("/owner/documents", headers=self.headers_owner1)
        docs1 = res1.json()
        self.assertTrue(len(docs1) > 0)
        doc_id = docs1[0]["id"]

        # Owner 1 can view their document detail
        detail_res = self.client.get(f"/owner/documents/{doc_id}", headers=self.headers_owner1)
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        self.assertEqual(detail_data["id"], doc_id)
        self.assertIn("extracted_text", detail_data)
        self.assertTrue(len(detail_data["extracted_text"]) > 0)

        # Multi-tenant isolation: Owner 2 MUST NOT be able to view Owner 1's document
        forbidden_res = self.client.get(f"/owner/documents/{doc_id}", headers=self.headers_owner2)
        self.assertEqual(forbidden_res.status_code, 403)
        self.assertIn("access denied", forbidden_res.json()["detail"].lower())

    def test_10_api_delete_document_and_multi_tenant_isolation(self):
        # Create a document for Owner 1 to test deletion
        file_payload = [
            ("files", ("temporary_to_delete.txt", io.BytesIO(b"This will be deleted"), "text/plain"))
        ]
        upload_res = self.client.post("/owner/documents", files=file_payload, headers=self.headers_owner1)
        self.assertEqual(upload_res.status_code, 200)
        new_doc_id = upload_res.json()["documents"][0]["id"]

        # Owner 2 attempts to delete Owner 1's document -> Must fail with 403
        del_forbidden = self.client.delete(f"/owner/documents/{new_doc_id}", headers=self.headers_owner2)
        self.assertEqual(del_forbidden.status_code, 403)

        # Owner 1 deletes their document -> Must succeed with 200
        del_res = self.client.delete(f"/owner/documents/{new_doc_id}", headers=self.headers_owner1)
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "success")

        # Document is gone
        get_res = self.client.get(f"/owner/documents/{new_doc_id}", headers=self.headers_owner1)
        self.assertEqual(get_res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
