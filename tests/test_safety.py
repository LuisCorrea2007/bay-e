import unittest

from app.core.safety import SAFETY


class SafetyGovernorTests(unittest.TestCase):
    def _state(self):
        return {
            "modules": [{"id": "motors", "enabled": False}],
            "settings": {"hardware": {"ros2_bridge": False}},
            "security": {"status": "ok"},
            "private_mode": False,
            "sensors": {"camera": True},
        }

    def test_stop_is_always_allowed(self):
        d = SAFETY.evaluate_motion("stop", self._state())
        self.assertTrue(d.allowed)
        self.assertEqual(d.normalized["dir"], "stop")

    def test_motion_without_hardware_is_blocked(self):
        d = SAFETY.evaluate_motion("up", self._state())
        self.assertFalse(d.allowed)
        self.assertEqual(d.code, "hardware_unavailable")

    def test_motion_with_hardware_can_be_allowed(self):
        s = self._state()
        s["modules"][0]["enabled"] = True
        s["settings"]["hardware"]["ros2_bridge"] = True
        d = SAFETY.evaluate_motion("forward", s)
        self.assertTrue(d.allowed)


if __name__ == "__main__":
    unittest.main()
