import unittest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import SessionLocal
from app.models import Reminder, Appointment, Customer, Business

client = TestClient(app)

class TestRemindersAPI(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_reminder_stats_and_delete_pending(self):
        # 1. Fetch current reminder stats
        res = client.get("/reminders/stats")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total", data)
        self.assertIn("pending", data)
        self.assertIn("sent", data)

        # 2. Test deleting pending reminders
        del_res = client.delete("/reminders/pending")
        self.assertEqual(del_res.status_code, 200)
        del_data = del_res.json()
        self.assertIn("deleted_count", del_data)

        # 3. Verify pending count is 0
        stats_after = client.get("/reminders/stats").json()
        self.assertEqual(stats_after["pending"], 0)

if __name__ == "__main__":
    unittest.main()
