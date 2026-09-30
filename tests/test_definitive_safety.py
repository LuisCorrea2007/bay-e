import unittest

from app.core.safety import SAFETY


class DefinitiveSafetyInvariantTests(unittest.TestCase):
    def live_state(self):
        return {
            "modules": [{"id": "motors", "enabled": True}],
            "settings": {
                "hardware": {"ros2_bridge": True},
                "security": {"max_speed": 0.6},
            },
            "security": {"status": "ok"},
            "hardware_connected": True,
            "software_estop": False,
            "private_mode": False,
            "sensors": {"camera": True},
        }

    def test_autonomous_unknown_object_is_never_grabbed(self):
        d = SAFETY.evaluate_manipulation(
            "left", self.live_state(),
            {"autonomous": True, "target": "objeto nuevo", "risk": "unknown"},
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.code, "unknown_object")

    def test_hazardous_object_is_blocked(self):
        d = SAFETY.evaluate_manipulation(
            "right", self.live_state(),
            {"target": "cuchillo de cocina", "risk": "hazardous"},
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.code, "hazardous_object")

    def test_pet_proximity_blocks_arm(self):
        d = SAFETY.evaluate_manipulation(
            "left", self.live_state(),
            {"target": "pelota", "risk": "safe", "pet_distance_m": 0.4},
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.code, "pet_proximity")

    def test_nearby_pet_reduces_motion_speed(self):
        d = SAFETY.evaluate_motion(
            "forward", self.live_state(),
            {"speed": 0.6, "pet_distance_m": 1.0},
        )
        self.assertTrue(d.allowed)
        self.assertLessEqual(d.normalized["speed"], 0.18)

    def test_safe_known_object_can_be_manipulated(self):
        d = SAFETY.evaluate_manipulation(
            "right", self.live_state(),
            {"autonomous": True, "target": "pelota", "risk": "safe"},
        )
        self.assertTrue(d.allowed)


if __name__ == "__main__":
    unittest.main()
