import time
import unittest

from app.cognition.intents import handle
from app.core import db
from app.core.diagnostics import snapshot as diagnostics_snapshot
from app.core.privacy import enforce_retention
from app.world.model import ingest_detection, snapshot as world_snapshot


class IntegrationFeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def test_explicit_memory_intent_mutates_memory_deterministically(self):
        marker = f"CI-memory-{time.time()}"
        out = handle(f"recuerda que {marker}")
        self.assertTrue(out.handled)
        self.assertIn("memory", out.payload or {})
        hits = db.list_memories(q=marker)
        self.assertTrue(any(marker in m["content"] for m in hits))

    def test_memory_query_intent_reads_confirmed_memory(self):
        marker = f"CI-query-{time.time()}"
        db.add_memory(type="semantic", content=f"{marker} está en pruebas", source="test", confidence=1.0)
        out = handle(f"qué recuerdas de {marker}?")
        self.assertTrue(out.handled)
        self.assertIn(marker, out.text)

    def test_task_intent_creates_task(self):
        marker = f"CI-task-{time.time()}"
        out = handle(f"crea una tarea {marker}")
        self.assertTrue(out.handled)
        self.assertTrue(any(marker in t["title"] for t in db.list_tasks()))

    def test_detection_updates_world_and_spatial_relation(self):
        marker = f"CI-object-{int(time.time()*1000)}"
        entity = ingest_detection({
            "label": marker,
            "kind": "object",
            "room": "ci_room",
            "confidence": 0.91,
            "ts": time.time(),
        })
        world = world_snapshot()
        self.assertTrue(any(e["id"] == entity["id"] for e in world["entities"]))
        room = next(e for e in world["entities"] if e["kind"] == "room" and e["label"] == "ci_room")
        self.assertTrue(any(
            r["subject_id"] == entity["id"] and r["predicate"] == "located_in" and r["object_id"] == room["id"]
            for r in world["relations"]
        ))

    def test_diagnostics_is_truthful_about_optional_capabilities(self):
        out = diagnostics_snapshot()
        self.assertIn("guardian", out)
        self.assertIn("models", out)
        self.assertIn("vision", out)
        self.assertIn("audio", out)
        self.assertIn("robot", out)
        self.assertIsInstance(out["robot"]["connected"], bool)

    def test_retention_keeps_recent_memory(self):
        marker = f"CI-retention-{time.time()}"
        mem = db.add_memory(type="episodic", content=marker, source="test", confidence=1.0)
        enforce_retention(3650)
        self.assertIsNotNone(db.get_memory(mem["id"]))


if __name__ == "__main__":
    unittest.main()
