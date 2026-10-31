"""devices: pairing, tokens, revocation and what reaches the disk."""
import os
import stat
import tempfile
import unittest
from pathlib import Path

from fetchd.api import devices
from fetchd.api.devices import Registry, TooManyPairings, UnknownCode, UnknownPairing


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "data" / "devices.json"
        self.clock = Clock()
        self.registry = Registry(self.path, self.clock)

    def tearDown(self):
        self.dir.cleanup()

    def paired_token(self, name="Living room TV"):
        pairing = self.registry.start_pairing(name)
        self.registry.approve(pairing.code)
        return self.registry.poll(pairing.pairing_id)

    def test_poll_waits_until_approved(self):
        pairing = self.registry.start_pairing("TV")
        self.assertIsNone(self.registry.poll(pairing.pairing_id))

    def test_approved_poll_returns_a_working_token(self):
        token = self.paired_token()
        self.assertIsNotNone(self.registry.authenticate(token))

    def test_token_is_handed_out_only_once(self):
        pairing = self.registry.start_pairing("TV")
        self.registry.approve(pairing.code)
        self.registry.poll(pairing.pairing_id)
        with self.assertRaises(UnknownPairing):
            self.registry.poll(pairing.pairing_id)

    def test_code_has_unambiguous_letters(self):
        code = self.registry.start_pairing("TV").code
        self.assertRegex(code, r"^[A-HJ-NP-Z2-9]{3}-[A-HJ-NP-Z2-9]{3}$")

    def test_approve_accepts_lowercase_without_dash(self):
        pairing = self.registry.start_pairing("TV")
        self.registry.approve(pairing.code.replace("-", "").lower())
        self.assertIsNotNone(self.registry.poll(pairing.pairing_id))

    def test_unknown_code_is_refused(self):
        with self.assertRaises(UnknownCode):
            self.registry.approve("AAA-AAA")

    def test_pairing_expires_after_ten_minutes(self):
        pairing = self.registry.start_pairing("TV")
        self.clock.now += devices.PAIRING_TTL_SECONDS + 1
        with self.assertRaises(UnknownPairing):
            self.registry.poll(pairing.pairing_id)

    def test_expired_code_cannot_be_approved(self):
        pairing = self.registry.start_pairing("TV")
        self.clock.now += devices.PAIRING_TTL_SECONDS + 1
        with self.assertRaises(UnknownCode):
            self.registry.approve(pairing.code)

    def test_pending_requests_are_capped(self):
        for _ in range(devices.MAX_PENDING):
            self.registry.start_pairing("TV")
        with self.assertRaises(TooManyPairings):
            self.registry.start_pairing("TV")

    def test_wrong_tokens_are_refused(self):
        self.paired_token()
        for token in ["", "fd1_", "fd1_" + "A" * 43, "Bearer x", None]:
            with self.subTest(token=token):
                self.assertIsNone(self.registry.authenticate(token))

    def test_revoked_token_stops_working(self):
        token = self.paired_token()
        device_id = self.registry.authenticate(token)
        self.assertTrue(self.registry.revoke(device_id))
        self.assertIsNone(self.registry.authenticate(token))

    def test_no_secret_is_written_to_disk(self):
        pairing = self.registry.start_pairing("TV")
        self.registry.approve(pairing.code)
        token = self.registry.poll(pairing.pairing_id)
        stored = self.path.read_text()
        self.assertNotIn(token, stored)
        self.assertNotIn(pairing.pairing_id, stored)

    def test_store_and_folder_are_private(self):
        self.paired_token()
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.path.parent).st_mode), 0o700)

    def test_device_name_is_cleaned(self):
        self.paired_token("Evil\x1b[31m name " + "x" * 200)
        name = self.registry.devices()[0]["name"]
        self.assertTrue(name.isprintable() and len(name) <= devices.MAX_DEVICE_NAME)

    def test_devices_list_has_no_secrets(self):
        self.paired_token()
        self.assertEqual(set(self.registry.devices()[0]), {"id", "name", "created", "lastSeen"})

    def test_last_seen_updates_at_most_hourly(self):
        token = self.paired_token()
        first = self.registry.devices()[0]["lastSeen"]
        self.clock.now += 60
        self.registry.authenticate(token)
        self.assertEqual(self.registry.devices()[0]["lastSeen"], first)


if __name__ == "__main__":
    unittest.main()
