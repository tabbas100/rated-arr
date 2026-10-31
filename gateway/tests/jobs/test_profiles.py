"""profiles: Up to 1080p and no disc images, against a fake Radarr."""
import json
import tempfile
import unittest
from pathlib import Path

from fetchd.jobs.profiles import UP_TO_1080P, WANTED, QualityProfiles


def quality(quality_id, name, allowed=False):
    return {"quality": {"id": quality_id, "name": name}, "items": [], "allowed": allowed}


def group(group_id, name, inner, allowed=False):
    return {"id": group_id, "name": name, "items": [quality(i, n, allowed) for i, n in inner], "allowed": allowed}


def schema():
    return {"name": "", "upgradeAllowed": False, "cutoff": 0, "items": [
        quality(1, "SDTV"), quality(2, "DVD"), group(1000, "WEB 480p", [(8, "WEBDL-480p"), (12, "WEBRip-480p")]),
        quality(20, "Bluray-480p"), quality(21, "Bluray-576p"), quality(4, "HDTV-720p"),
        group(1001, "WEB 720p", [(5, "WEBDL-720p"), (14, "WEBRip-720p")]), quality(6, "Bluray-720p"),
        quality(9, "HDTV-1080p"), group(1002, "WEB 1080p", [(3, "WEBDL-1080p"), (15, "WEBRip-1080p")]),
        quality(7, "Bluray-1080p"), quality(30, "Remux-1080p"), quality(19, "Bluray-2160p"), quality(22, "BR-DISK")]}


def profile(profile_id, name, allowed_names, cutoff=20):
    built = schema()
    built.update({"id": profile_id, "name": name, "cutoff": cutoff})
    for item in built["items"]:
        item["allowed"] = (item.get("name") or item["quality"]["name"]) in allowed_names
    return built


class FakeRadarr:
    name = "Radarr"

    def __init__(self, profiles):
        self.profiles = profiles
        self.writes = []

    def get(self, path, **query):
        return schema() if path.endswith("/schema") else self.profiles

    def post(self, path, body):
        self.writes.append(("POST", path, body))

    def put(self, path, body):
        self.writes.append(("PUT", path, body))


class QualityProfilesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.backups = Path(self.dir.name) / "backup"

    def tearDown(self):
        self.dir.cleanup()

    def set_up(self, *profiles):
        radarr = FakeRadarr(list(profiles))
        changes = QualityProfiles(radarr, self.backups).set_up()
        return radarr, changes

    def up_to_1080p(self):
        return profile(7, UP_TO_1080P, WANTED, cutoff=1002) | {"upgradeAllowed": True}

    def test_a_missing_profile_is_created_from_the_schema(self):
        radarr, _ = self.set_up(profile(1, "Any", {"SDTV"}))
        method, path, body = radarr.writes[0]
        self.assertEqual((method, path, body["name"]), ("POST", "/api/v3/qualityprofile", UP_TO_1080P))

    def test_the_new_profile_allows_exactly_sd_to_1080p(self):
        radarr, _ = self.set_up(profile(1, "Any", {"SDTV"}))
        allowed = {item.get("name") or item["quality"]["name"] for item in radarr.writes[0][2]["items"] if item["allowed"]}
        self.assertEqual(allowed, WANTED)

    def test_the_new_profile_upgrades_until_web_1080p(self):
        radarr, _ = self.set_up(profile(1, "Any", {"SDTV"}))
        body = radarr.writes[0][2]
        self.assertEqual((body["upgradeAllowed"], body["cutoff"]), (True, 1002))

    def test_a_matching_profile_is_left_alone(self):
        radarr, changes = self.set_up(self.up_to_1080p())
        self.assertEqual((radarr.writes, changes), ([], []))

    def test_a_different_profile_of_that_name_is_updated(self):
        radarr, changes = self.set_up(profile(7, UP_TO_1080P, {"SDTV"}))
        self.assertEqual((radarr.writes[0][:2], changes), (("PUT", "/api/v3/qualityprofile/7"), ["Radarr: updated Up to 1080p"]))

    def test_disc_images_are_refused(self):
        radarr, _ = self.set_up(self.up_to_1080p(), profile(1, "Any", {"SDTV", "BR-DISK"}))
        disc = next(item for item in radarr.writes[0][2]["items"] if item.get("quality", {}).get("name") == "BR-DISK")
        self.assertFalse(disc["allowed"])

    def test_a_profile_is_backed_up_before_it_changes(self):
        self.set_up(self.up_to_1080p(), profile(1, "Any", {"SDTV", "BR-DISK"}))
        saved = json.loads(next(self.backups.glob("radarr-qualityprofile-1-*.json")).read_text())
        self.assertEqual(saved["name"], "Any")

    def test_a_profile_cut_off_at_disc_images_is_left_alone(self):
        radarr, changes = self.set_up(self.up_to_1080p(), profile(1, "Discs", {"BR-DISK"}, cutoff=22))
        self.assertEqual((radarr.writes, changes), ([], ["Radarr: left Discs alone, its cutoff is BR-DISK"]))


if __name__ == "__main__":
    unittest.main()
