"""Key migration and secret loss must be safe across restarts."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from scripts import bootstrap


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        private = root / "private" / "jwt-private.pem"
        public = root / "public" / "jwt-public.pem"
        legacy = root / "legacy"
        for directory in (private.parent, public.parent, legacy):
            directory.mkdir()
        for name, value in (
            ("PRIVATE", private),
            ("PUBLIC", public),
            ("LEGACY", legacy),
        ):
            replacement = patch.object(bootstrap, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.private = private
        self.public = public
        self.legacy = legacy

    def test_clean_install_and_interrupted_publication(self) -> None:
        bootstrap.init_keys(existing_database=False)
        original = self.private.read_bytes()
        self.public.unlink()
        bootstrap.init_keys(existing_database=True)
        self.assertEqual(self.private.read_bytes(), original)
        self.assertEqual(
            serialization.load_pem_public_key(
                self.public.read_bytes()
            ).public_numbers(),
            bootstrap.load_private(self.private).public_key().public_numbers(),
        )

    def test_missing_private_key_does_not_rotate_existing_database(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "restore original key"):
            bootstrap.init_keys(existing_database=True)
        self.assertFalse(self.private.exists())

    def test_migrate_legacy_pair_without_changing_it(self) -> None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        old_private = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        old_public = bootstrap.public_bytes(key)
        (self.legacy / "jwt-private.pem").write_bytes(old_private)
        (self.legacy / "jwt-public.pem").write_bytes(old_public)
        bootstrap.init_keys(existing_database=True)
        self.assertEqual(self.private.read_bytes(), old_private)
        self.assertEqual(self.public.read_bytes(), old_public)

    def test_missing_password_with_existing_database_fails(self) -> None:
        path = Path(self.directory.name) / "password"
        with self.assertRaisesRegex(RuntimeError, "Missing secret"):
            bootstrap.init_secret(path, database_exists=True)
        self.assertFalse(path.exists())
        bootstrap.init_secret(path, database_exists=False)
        original = path.read_bytes()
        bootstrap.init_secret(path, database_exists=True)
        self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
