import time
import unittest

from app.core import db


class ChatMindMobileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def test_chat_thread_message_edit_delete(self):
        t = db.create_thread("Prueba chat")
        m = db.add_message("user", "hola original", thread_id=t["id"])
        self.assertEqual(db.list_messages(thread_id=t["id"])[-1]["content"], "hola original")
        edited = db.update_message(m["id"], "hola editado")
        self.assertEqual(edited["content"], "hola editado")
        self.assertTrue(db.delete_message(m["id"]))
        self.assertFalse(any(x["id"] == m["id"] for x in db.list_messages(thread_id=t["id"])))
        self.assertTrue(db.delete_thread(t["id"]))

    def test_chat_search_finds_message_and_thread(self):
        marker = "buscar-" + str(time.time_ns())
        t = db.create_thread("Chat buscable")
        m = db.add_message("user", "contenido " + marker, thread_id=t["id"])
        hits = db.search_messages(marker)
        self.assertTrue(any(x["id"] == m["id"] and x["thread_id"] == t["id"] for x in hits))
        self.assertTrue(db.delete_thread(t["id"]))

    def test_mind_rule_crud(self):
        r = db.add_mind_rule("restriction", "No inventar acciones físicas.", priority=95)
        self.assertTrue(r["enabled"])
        self.assertEqual(r["kind"], "restriction")
        r2 = db.update_mind_rule(r["id"], content="No inventar acciones ni sensores.", enabled=False)
        self.assertFalse(r2["enabled"])
        self.assertIn("sensores", r2["content"])
        self.assertTrue(db.delete_mind_rule(r["id"]))

    def test_mobile_node_upsert(self):
        node = db.upsert_mobile_node(
            "test-phone",
            name="Teléfono test",
            platform="android",
            capabilities={"camera": True, "microphone": True},
            telemetry={"battery": {"batteryLevel": 0.8}},
        )
        self.assertEqual(node["id"], "test-phone")
        self.assertTrue(node["capabilities"]["camera"])
        nodes = db.list_mobile_nodes()
        self.assertTrue(any(n["id"] == "test-phone" for n in nodes))


if __name__ == "__main__":
    unittest.main()
