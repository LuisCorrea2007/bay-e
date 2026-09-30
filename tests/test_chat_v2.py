import os
import unittest
from unittest.mock import patch

from app.cognition.chat_commands import parse
from app.cognition.model_router import OpenAIResponsesProvider


class ChatCommandTests(unittest.TestCase):
    def state(self):
        return {
            "emotions": {"energy": .8, "curiosity": .7, "mood": .75},
            "expression": {"emotion": "happy"},
            "_recent_dets": [{"label": "taza", "kind": "object", "confidence": .9}],
        }

    def test_open_memory_navigation(self):
        out = parse("abre memoria", self.state())
        self.assertTrue(out.handled)
        self.assertEqual(out.ui_action, "memory")

    def test_explore_becomes_safe_brain_command(self):
        out = parse("explora la casa", self.state())
        self.assertTrue(out.handled)
        self.assertEqual(out.brain_command, "set_mode")
        self.assertEqual(out.brain_payload["mode"], "explore")

    def test_stop_is_real_motion_command(self):
        out = parse("detente", self.state())
        self.assertTrue(out.handled)
        self.assertEqual(out.brain_command, "move")
        self.assertEqual(out.brain_payload["dir"], "stop")

    def test_vision_reports_confirmed_detection(self):
        out = parse("qué ves ahora?", self.state())
        self.assertTrue(out.handled)
        self.assertIn("taza", out.text)


class OpenAIProviderTests(unittest.TestCase):
    def test_extracts_responses_api_output(self):
        payload = {
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "Hola desde BAY-E"}],
            }]
        }
        self.assertEqual(OpenAIResponsesProvider._extract_text(payload), "Hola desde BAY-E")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    def test_provider_never_exposes_key_in_public_fields(self):
        p = OpenAIResponsesProvider({"openai_model": "gpt-6-luna"})
        self.assertTrue(p.enabled)
        self.assertNotIn("test-key", p.base)
        self.assertNotIn("test-key", p.model)


if __name__ == "__main__":
    unittest.main()
