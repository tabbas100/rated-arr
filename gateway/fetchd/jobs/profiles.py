"""Quality profiles a Plex library wants, set up once with `fetchd setup-profiles`.

"Up to 1080p" takes anything from SD to 1080p, so old and obscure titles that exist only in SD can be
found, and upgrades until a WEB 1080p copy arrives. It takes no 4K, remuxes or disc images. Disc images
(BR-DISK) are whole Blu-ray .iso files that Plex cannot play or list, so every profile is set to refuse
them. Each profile is saved to the backup folder before it changes; running it again changes nothing.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Callable

from ..arr.library import allows_disc_images
from ..upstream import Upstream

UP_TO_1080P = "Up to 1080p"
WANTED = {"SDTV", "DVD", "WEB 480p", "Bluray-480p", "Bluray-576p", "HDTV-720p", "WEB 720p", "Bluray-720p",
          "HDTV-1080p", "WEB 1080p", "Bluray-1080p"}
CUTOFF = "WEB 1080p"


class QualityProfiles:
    def __init__(self, app: Upstream, backups: Path, clock: Callable[[], float] = time.time) -> None:
        self.app = app
        self.backups = backups
        self.clock = clock

    def set_up(self) -> list[str]:
        """Makes Up to 1080p and refuses disc images everywhere; one line per change, none when all was set."""
        changes = [self._up_to_1080p()]
        changes += [self._refuse_disc_images(profile) for profile in self._profiles() if allows_disc_images(profile)]
        return [change for change in changes if change]

    def _up_to_1080p(self) -> str:
        existing = next((p for p in self._profiles() if str(p.get("name", "")).lower() == UP_TO_1080P.lower()), None)
        template = existing if existing else self.app.get("/api/v3/qualityprofile/schema")
        wanted = _up_to_1080p_from(template)
        if existing is None:
            self.app.post("/api/v3/qualityprofile", wanted)
            return f"{self.app.name}: created {UP_TO_1080P}"
        if _same_choice(existing, wanted):
            return ""
        self._back_up(existing)
        self.app.put(f"/api/v3/qualityprofile/{existing['id']}", wanted)
        return f"{self.app.name}: updated {UP_TO_1080P}"

    def _refuse_disc_images(self, profile: dict) -> str:
        if _name_of(profile, profile.get("cutoff")).upper() == "BR-DISK":
            return f"{self.app.name}: left {profile.get('name')} alone, its cutoff is BR-DISK"
        refused = copy.deepcopy(profile)
        for item in _qualities(refused):
            if _item_name(item).upper() == "BR-DISK":
                item["allowed"] = False
        self._back_up(profile)
        self.app.put(f"/api/v3/qualityprofile/{profile['id']}", refused)
        return f"{self.app.name}: {profile.get('name')} no longer takes disc images (BR-DISK)"

    def _profiles(self) -> list[dict]:
        return [p for p in self.app.get("/api/v3/qualityprofile") or [] if isinstance(p, dict) and "id" in p]

    def _back_up(self, profile: dict) -> None:
        self.backups.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(self.clock()))
        path = self.backups / f"{self.app.name.lower()}-qualityprofile-{profile['id']}-{stamp}.json"
        path.write_text(json.dumps(profile, indent=2), "utf-8")


def _up_to_1080p_from(template: dict) -> dict:
    """The template with exactly the wanted qualities allowed, upgrades on and the cutoff at WEB 1080p."""
    profile = copy.deepcopy(template)
    profile["name"] = UP_TO_1080P
    profile["upgradeAllowed"] = True
    for item in profile.get("items") or []:
        allowed = _item_name(item) in WANTED
        item["allowed"] = allowed
        for inner in item.get("items") or []:
            inner["allowed"] = allowed
    profile["cutoff"] = next(_item_id(item) for item in profile["items"] if _item_name(item) == CUTOFF)
    return profile


def _same_choice(current: dict, wanted: dict) -> bool:
    """True when both allow the same qualities, cut off at the same one and both upgrade."""
    return (_allowed_names(current) == _allowed_names(wanted) and current.get("cutoff") == wanted.get("cutoff")
            and bool(current.get("upgradeAllowed")) == bool(wanted.get("upgradeAllowed")))


def _allowed_names(profile: dict) -> set[str]:
    return {_item_name(item) for item in profile.get("items") or [] if item.get("allowed")}


def _qualities(profile: dict) -> list[dict]:
    """Every entry: the top-level ones and those inside groups such as "WEB 1080p"."""
    out = []
    for item in profile.get("items") or []:
        out.append(item)
        out.extend(item.get("items") or [])
    return out


def _item_name(item: dict) -> str:
    """A group's own name ("WEB 1080p"), or the quality's ("Bluray-1080p")."""
    if item.get("items"):
        return str(item.get("name", ""))
    return str((item.get("quality") or {}).get("name", ""))


def _item_id(item: dict) -> int:
    return item["id"] if item.get("items") else (item.get("quality") or {})["id"]


def _name_of(profile: dict, item_id: object) -> str:
    return next((_item_name(item) for item in profile.get("items") or [] if _item_id(item) == item_id), "")
