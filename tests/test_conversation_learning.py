import uuid
import unittest

from app.core import db
from app.learning.conversation import propose


class ConversationLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def test_preference_is_proposed_not_immediately_memorized(self):
        marker = "sopa-" + uuid.uuid4().hex[:8]
        candidate = propose("Me gusta " + marker, "msg_test")
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["status"], "pending")
        self.assertEqual(candidate["kind"], "semantic")
        self.assertFalse(any(m["content"] == candidate["content"] for m in db.list_memories()))

        approved = db.resolve_learning_candidate(candidate["id"], "approve")
        self.assertEqual(approved["status"], "approved")
        memory = db.get_memory(approved["memory_id"])
        self.assertIsNotNone(memory)
        self.assertEqual(memory["source"], "learning-review")
        self.assertIn("user-approved", memory["tags"])

    def test_sensitive_information_is_not_proposed(self):
        self.assertIsNone(propose("Mi contraseña es supersecreta123", "msg_sensitive"))
        self.assertIsNone(propose("Normalmente reviso mi cuenta bancaria a las 8", "msg_sensitive2"))

    def test_rejected_candidate_does_not_create_memory(self):
        marker = "verde-" + uuid.uuid4().hex[:8]
        candidate = propose("Prefiero " + marker, "msg_reject")
        self.assertIsNotNone(candidate)
        rejected = db.resolve_learning_candidate(candidate["id"], "reject")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["memory_id"], "")


if __name__ == "__main__":
    unittest.main()
