import unittest

from app.core import db
from app.core.events import EventBus
from app.health.service import record, trend
from app.world.model import upsert_entity, snapshot


class CoreServicesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def test_event_bus_delivers(self):
        bus = EventBus()
        seen = []
        bus.subscribe("x", lambda e: seen.append(e.payload["value"]))
        bus.publish("x", {"value": 7})
        self.assertEqual(seen, [7])

    def test_world_entity_is_persistent_and_deduplicated(self):
        a = upsert_entity("object", "Test Object", source="test", confidence=.4)
        b = upsert_entity("object", "test object", source="test", confidence=.8)
        self.assertEqual(a["id"], b["id"])
        self.assertGreaterEqual(float(b["confidence"]), .8)
        self.assertTrue(any(e["id"] == a["id"] for e in snapshot()["entities"]))

    def test_health_trend_is_descriptive(self):
        record("test_metric", 10, "u", source="test")
        record("test_metric", 12, "u", source="test")
        out = trend("test_metric")
        self.assertGreaterEqual(out["count"], 2)
        self.assertIn("no constituye diagnóstico", out["notice"])


if __name__ == "__main__":
    unittest.main()
