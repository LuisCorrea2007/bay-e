import unittest
from pathlib import Path

from main import _versioned_api_path, app


class ApiVersioningTests(unittest.TestCase):
    def test_v1_routes_are_mounted(self):
        paths = {getattr(route, "path", "") for route in app.routes}
        self.assertIn("/api/v1/state", paths)
        self.assertIn("/api/v1/chat/send", paths)

    def test_legacy_alias_rewrites_to_v1(self):
        self.assertEqual(_versioned_api_path("/api/state"), "/api/v1/state")
        self.assertEqual(_versioned_api_path("/api/chat/send"), "/api/v1/chat/send")
        self.assertEqual(_versioned_api_path("/api/v1/state"), "/api/v1/state")
        self.assertEqual(_versioned_api_path("/health"), "/health")

    def test_openapi_documents_only_v1_contract(self):
        paths = app.openapi().get("paths", {})
        self.assertIn("/api/v1/state", paths)
        self.assertIn("/api/v1/chat/send", paths)
        self.assertNotIn("/api/state", paths)
        self.assertNotIn("/api/chat/send", paths)

    def test_first_party_clients_use_v1(self):
        root = Path(__file__).resolve().parents[1]
        for rel in ("static/js/app.js", "static/js/views.js", "mobile/src/main.js"):
            text = (root / rel).read_text(encoding="utf-8")
            self.assertIn("/api/v1/", text, rel)
            self.assertNotIn("/api/", text.replace("/api/v1/", ""), rel)


if __name__ == "__main__":
    unittest.main()
