import os
import unittest
from unittest.mock import patch

from app.cognition.model_router import ModelRouter


class ModelRouterOpenAITests(unittest.TestCase):
    def test_openai_provider_is_configured_without_leaking_secret(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-secret-not-real"}, clear=False):
            router = ModelRouter()
            router.configure({"provider_order": "openai", "openai_model": "gpt-6-luna"})
            status = router.status()
            self.assertEqual(status["providers"][0]["name"], "openai")
            self.assertTrue(status["providers"][0]["configured"])
            self.assertNotIn("test-secret-not-real", str(status))

    def test_router_falls_back_when_openai_key_missing(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            router = ModelRouter()
            router.configure({"provider_order": "openai"})
            out = router.generate([{"role": "user", "content": "hola"}])
            self.assertEqual(out.provider, "fallback")
            self.assertTrue(out.degraded)


if __name__ == "__main__":
    unittest.main()
