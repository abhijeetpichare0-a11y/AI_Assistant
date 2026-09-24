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

    def test_stop_and_resume_reminders(self):
        # Test stop endpoint
        stop_res = client.post("/reminders/stop")
        self.assertEqual(stop_res.status_code, 200)
        self.assertFalse(stop_res.json()["scheduler_active"])

        # Check status endpoint
        status_res = client.get("/reminders/scheduler-status")
        self.assertEqual(status_res.status_code, 200)
        self.assertFalse(status_res.json()["scheduler_active"])

        # Test resume endpoint
        start_res = client.post("/reminders/start")
        self.assertEqual(start_res.status_code, 200)
        self.assertTrue(start_res.json()["scheduler_active"])

        # Stop again to keep stopped as requested
        stop_again = client.post("/reminders/stop")
        self.assertEqual(stop_again.status_code, 200)
        self.assertFalse(stop_again.json()["scheduler_active"])

if __name__ == "__main__":
    unittest.main()
