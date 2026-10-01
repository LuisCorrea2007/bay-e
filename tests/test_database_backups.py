import tempfile
import unittest
from pathlib import Path

from app.core import db


class DatabaseBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        self.old_init = db._INIT_DB_DONE
        db.DB_PATH = Path(self.tmp.name) / "baye-test.db"
        db._INIT_DB_DONE = False
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_path
        db._INIT_DB_DONE = self.old_init
        self.tmp.cleanup()

    def test_wal_and_full_snapshot_restore(self):
        health = db.database_health()
        self.assertTrue(health["ok"])
        self.assertEqual(health["journal_mode"].lower(), "wal")

        original = db.add_memory(
            type="semantic",
            content="snapshot sentinel",
            source="test",
            confidence=1.0,
        )
        db.add_message("user", "mensaje antes del backup")

        backup = Path(self.tmp.name) / "snapshot.sqlite3"
        meta = db.create_database_backup(backup)
        self.assertEqual(meta["integrity"], "ok")
        self.assertTrue(backup.is_file())

        db.delete_memory(original["id"])
        db.add_message("user", "mensaje que debe desaparecer")

        restored = db.restore_database_backup(backup)
        self.assertTrue(restored["ok"])
        self.assertTrue(restored["restart_required"])

        memories = db.list_memories(q="snapshot sentinel")
        self.assertEqual(len(memories), 1)
        messages = [m["content"] for m in db.list_messages(100)]
        self.assertIn("mensaje antes del backup", messages)
        self.assertNotIn("mensaje que debe desaparecer", messages)

    def test_corrupt_snapshot_is_rejected_without_touching_live_db(self):
        db.add_memory(type="semantic", content="live sentinel", source="test")
        bad = Path(self.tmp.name) / "bad.sqlite3"
        bad.write_bytes(b"not a sqlite database")

        with self.assertRaises(Exception):
            db.restore_database_backup(bad)

        self.assertEqual(len(db.list_memories(q="live sentinel")), 1)


if __name__ == "__main__":
    unittest.main()
