import uuid
import unittest

from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes import _require_mobile, mobile_location
from app.core import db
from app.core.mobile_auth import claim_pairing_code, create_pairing_code, token_hash


def request_with_token(token: str = "") -> Request:
    headers = []
    if token:
        headers.append((b"authorization", ("Bearer " + token).encode("utf-8")))
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/mobile/test",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8300),
        "scheme": "http",
        "query_string": b"",
    })


class MobilePairingSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def test_pairing_is_one_time_and_required(self):
        node_id = "test-secure-" + uuid.uuid4().hex[:8]
        pairing = create_pairing_code(60)
        self.assertRegex(pairing["code"], r"^\d{6}$")

        token = claim_pairing_code(pairing["code"])
        self.assertIsNotNone(token)
        self.assertIsNone(claim_pairing_code(pairing["code"]))

        node = db.pair_mobile_node(
            node_id,
            name="Android test",
            platform="android",
            token_hash=token_hash(token),
        )
        self.assertTrue(node["paired"])
        self.assertNotIn("token_hash", node)

        with self.assertRaises(HTTPException) as no_auth:
            _require_mobile(request_with_token(), node_id)
        self.assertEqual(no_auth.exception.status_code, 401)

        auth = _require_mobile(request_with_token(token), node_id)
        self.assertEqual(auth["id"], node_id)

        public = db.get_mobile_node(node_id)
        self.assertNotIn("token_hash", public)
        self.assertTrue(public["paired"])

        self.assertTrue(db.revoke_mobile_node(node_id))
        with self.assertRaises(HTTPException) as revoked:
            _require_mobile(request_with_token(token), node_id)
        self.assertEqual(revoked.exception.status_code, 401)

    def test_location_is_ephemeral_by_default(self):
        node_id = "test-location-" + uuid.uuid4().hex[:8]
        code = create_pairing_code(60)["code"]
        token = claim_pairing_code(code)
        db.pair_mobile_node(
            node_id,
            name="Location test",
            platform="android",
            token_hash=token_hash(token),
        )
        response = mobile_location(request_with_token(token), {
            "node_id": node_id,
            "lat": -2.170998,
            "lon": -79.922359,
            "remember": False,
        })
        self.assertTrue(response["ok"])
        self.assertFalse(response["remembered"])
        self.assertIsNone(response["memory_id"])


if __name__ == "__main__":
    unittest.main()
