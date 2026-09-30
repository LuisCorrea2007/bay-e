import unittest

from app.core import db
from app.memory.relationship import context_block, observe_user_turn


class RelationshipContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def test_non_sensitive_milestone_is_recorded(self):
        item = observe_user_turn("Gracias BAY-E", "msg_test_relationship")
        self.assertIsNotNone(item)
        self.assertEqual(item["kind"], "gratitude")
        self.assertIn("agradecimiento", item["summary"])
        self.assertIn("continuity", item["tags"])
        self.assertIn("agradecimiento", context_block())

    def test_sensitive_context_is_not_recorded(self):
        item = observe_user_turn("Gracias, mi contraseña es supersecreta", "msg_sensitive")
        self.assertIsNone(item)

    def test_summary_has_no_secret_hash_fields(self):
        summary = db.relationship_summary(limit=5)
        self.assertIn("recent_events", summary)
        self.assertIn("approved_memory_count", summary)


if __name__ == "__main__":
    unittest.main()
