import uuid
import unittest

from fastapi.testclient import TestClient

from main import app


class MobilePairingSecurityTests(unittest.TestCase):
    def test_pairing_is_one_time_and_required_for_mobile_endpoints(self):
        node_id = "test-secure-" + uuid.uuid4().hex[:8]
        with TestClient(app) as client:
            started = client.post("/api/mobile/pair/start", json={"ttl_seconds": 60})
            self.assertEqual(started.status_code, 200)
            code = started.json()["code"]
            self.assertRegex(code, r"^\d{6}$")

            claim = client.post("/api/mobile/pair/claim", json={
                "id": node_id,
                "code": code,
                "name": "Android test",
                "platform": "android",
            })
            self.assertEqual(claim.status_code, 200)
            token = claim.json()["token"]
            self.assertGreater(len(token), 30)
            self.assertNotIn("token_hash", claim.json()["node"])
            self.assertTrue(claim.json()["node"]["paired"])

            reused = client.post("/api/mobile/pair/claim", json={
                "id": node_id + "-other",
                "code": code,
                "name": "Replay",
                "platform": "android",
            })
            self.assertEqual(reused.status_code, 401)

            heartbeat_payload = {
                "id": node_id,
                "name": "Android test",
                "platform": "android",
                "capabilities": {"camera": True, "microphone": True},
                "telemetry": {"battery": {"batteryLevel": 0.7}},
            }
            no_auth = client.post("/api/mobile/heartbeat", json=heartbeat_payload)
            self.assertEqual(no_auth.status_code, 401)

            headers = {"Authorization": "Bearer " + token}
            ok = client.post("/api/mobile/heartbeat", json=heartbeat_payload, headers=headers)
            self.assertEqual(ok.status_code, 200)
            self.assertTrue(ok.json()["node"]["paired"])
            self.assertNotIn("token_hash", ok.json()["node"])

            history = client.get(
                "/api/mobile/chat/history",
                params={"node_id": node_id, "thread_id": "default"},
                headers=headers,
            )
            self.assertEqual(history.status_code, 200)

            revoked = client.delete("/api/mobile/nodes/" + node_id)
            self.assertEqual(revoked.status_code, 200)

            after_revoke = client.post("/api/mobile/heartbeat", json=heartbeat_payload, headers=headers)
            self.assertEqual(after_revoke.status_code, 401)

    def test_location_is_ephemeral_by_default(self):
        node_id = "test-location-" + uuid.uuid4().hex[:8]
        with TestClient(app) as client:
            code = client.post("/api/mobile/pair/start", json={}).json()["code"]
            claim = client.post("/api/mobile/pair/claim", json={
                "id": node_id, "code": code, "name": "Location test", "platform": "android",
            })
            token = claim.json()["token"]
            headers = {"Authorization": "Bearer " + token}
            response = client.post("/api/mobile/location", json={
                "node_id": node_id, "lat": -2.170998, "lon": -79.922359, "remember": False,
            }, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["remembered"])
            self.assertIsNone(response.json()["memory_id"])


if __name__ == "__main__":
    unittest.main()
