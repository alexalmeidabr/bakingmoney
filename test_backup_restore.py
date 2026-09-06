import os
import tempfile
import unittest
from unittest import mock

import web_server


class BackupRestoreValidationTests(unittest.TestCase):
    def test_validate_backup_db_file_accepts_initialized_database(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "valid.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
            web_server._validate_backup_db_file(db_path)

    def test_validate_backup_db_file_rejects_non_sqlite_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = os.path.join(tmpdir, "fake.db")
            with open(fake_path, "wb") as handle:
                handle.write(b"not-a-sqlite-file")

            with self.assertRaisesRegex(ValueError, "not a valid SQLite"):
                web_server._validate_backup_db_file(fake_path)

    def test_validate_backup_db_file_rejects_missing_required_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "missing-tables.db")
            conn = web_server.sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE example (id INTEGER PRIMARY KEY)")
                conn.commit()
            finally:
                conn.close()

            with self.assertRaisesRegex(ValueError, "missing required table"):
                web_server._validate_backup_db_file(db_path)

    def test_create_db_backup_snapshot_writes_valid_copy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = os.path.join(tmpdir, "source.db")
            destination_path = os.path.join(tmpdir, "snapshot.db")
            conn = web_server.sqlite3.connect(source_path)
            try:
                conn.execute("CREATE TABLE notes (value TEXT)")
                conn.execute("INSERT INTO notes (value) VALUES ('backup-test')")
                conn.commit()
            finally:
                conn.close()

            web_server._create_db_backup_snapshot(source_path, destination_path)

            copied_conn = web_server.sqlite3.connect(destination_path)
            try:
                row = copied_conn.execute("SELECT value FROM notes").fetchone()
            finally:
                copied_conn.close()
            self.assertEqual(row[0], "backup-test")

    def test_build_backup_manifest_reports_env_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "manifest.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                manifest = web_server._build_backup_manifest(True)
        self.assertEqual(manifest["app_name"], "BakingMoney")
        self.assertIn("exported_at", manifest)
        self.assertTrue(manifest["includes_env"])
        self.assertIn("schema_version", manifest)

    def test_initialized_database_includes_frontier_optionality_for_backup_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "frontier.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
            conn = web_server.sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_frontier_optionality'"
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)

    def test_older_backup_without_frontier_optionality_table_can_be_migrated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "older-backup.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
            conn = web_server.sqlite3.connect(db_path)
            try:
                conn.execute("DROP TABLE analysis_frontier_optionality")
                conn.commit()
            finally:
                conn.close()

            web_server._validate_backup_db_file(db_path)

            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
            conn = web_server.sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_frontier_optionality'"
                ).fetchone()
            finally:
                conn.close()
            self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
