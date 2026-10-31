"""Paired TVs and pairing requests, stored as hashes in one JSON file.

A TV asks to pair and shows a short code. The owner approves that code over SSH with the admin
command, which proves they control the box. The TV's next poll then receives a device token once.
Only SHA-256 hashes of tokens and pairing ids are written to disk.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

TOKEN_PREFIX = "fd1_"
PAIRING_TTL_SECONDS = 600
MAX_PENDING = 5
LAST_SEEN_EVERY_SECONDS = 3600
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_DEVICE_NAME = 60


class UnknownPairing(Exception):
    """The pairing id is unknown or has expired."""


class TooManyPairings(Exception):
    """Too many pairing requests are waiting for approval."""


class UnknownCode(Exception):
    """No waiting pairing request has that code."""


@dataclass(frozen=True)
class Pairing:
    pairing_id: str
    code: str
    expires_in: int


class Registry:
    """The device and pairing store. Safe to share between the server and the admin command."""

    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self.clock = clock

    def start_pairing(self, device_name: str) -> Pairing:
        """Registers a pairing request and returns its secret id and the code the TV shows."""
        pairing_id = secrets.token_urlsafe(32)
        with self._state() as state:
            pending = state["pairings"]
            if len(pending) >= MAX_PENDING:
                raise TooManyPairings()
            code = _new_code({p["code"] for p in pending.values()})
            pending[_hash(pairing_id)] = {
                "code": code,
                "device": _clean_name(device_name),
                "created": self.clock(),
                "approved": False,
            }
        return Pairing(pairing_id, code, PAIRING_TTL_SECONDS)

    def poll(self, pairing_id: str) -> str | None:
        """The new device token once the code is approved (only once), None while it waits."""
        with self._state() as state:
            entry = state["pairings"].get(_hash(pairing_id))
            if entry is None:
                raise UnknownPairing()
            if not entry["approved"]:
                return None
            del state["pairings"][_hash(pairing_id)]
            return self._register_device(state, entry["device"])

    def pending(self) -> list[dict]:
        """Waiting requests, oldest first, as {code, device, age} for the admin command."""
        with self._state() as state:
            entries = sorted(state["pairings"].values(), key=lambda e: e["created"])
            return [
                {"code": e["code"], "device": e["device"], "age": int(self.clock() - e["created"]),
                 "approved": e["approved"]}
                for e in entries
            ]

    def approve(self, code: str) -> str:
        """Approves the waiting request with this code and returns its device name."""
        wanted = _normalize_code(code)
        with self._state() as state:
            for entry in state["pairings"].values():
                if entry["code"] == wanted and not entry["approved"]:
                    entry["approved"] = True
                    return entry["device"]
        raise UnknownCode(code)

    def authenticate(self, token: str) -> str | None:
        """The device id for a valid token, None otherwise."""
        if not _looks_like_token(token):
            return None
        token_hash = _hash(token)
        with self._state() as state:
            device = state["devices"].get(token_hash)
            if device is None:
                return None
            if self.clock() - device.get("lastSeen", 0) > LAST_SEEN_EVERY_SECONDS:
                device["lastSeen"] = self.clock()
            return device["id"]

    def devices(self) -> list[dict]:
        """Paired devices as {id, name, created, lastSeen}, without any secret."""
        with self._state() as state:
            return sorted((dict(d) for d in state["devices"].values()), key=lambda d: d["created"])

    def revoke(self, device_id: str) -> bool:
        """Removes a device; its token stops working at once."""
        with self._state() as state:
            for token_hash, device in list(state["devices"].items()):
                if device["id"] == device_id:
                    del state["devices"][token_hash]
                    return True
        return False

    def _register_device(self, state: dict, name: str) -> str:
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        state["devices"][_hash(token)] = {
            "id": secrets.token_hex(4),
            "name": name,
            "created": self.clock(),
            "lastSeen": self.clock(),
        }
        return token

    @contextmanager
    def _state(self) -> Iterator[dict]:
        """The store under an exclusive file lock; written back atomically if the block changed it."""
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(".lock")
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            before = self._read()
            state = json.loads(before)
            self._expire_pairings(state)
            yield state
            after = json.dumps(state, sort_keys=True)
            if after != before:
                self._write(after)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def _read(self) -> str:
        try:
            state = json.loads(self.path.read_text("utf-8"))
        except FileNotFoundError:
            state = {}
        state.setdefault("devices", {})
        state.setdefault("pairings", {})
        return json.dumps(state, sort_keys=True)

    def _write(self, text: str) -> None:
        temp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, self.path)

    def _expire_pairings(self, state: dict) -> None:
        now = self.clock()
        state["pairings"] = {
            key: entry for key, entry in state["pairings"].items()
            if now - entry["created"] < PAIRING_TTL_SECONDS
        }


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _looks_like_token(token: str) -> bool:
    return isinstance(token, str) and token.startswith(TOKEN_PREFIX) and 40 <= len(token) <= 80


def _new_code(taken: set) -> str:
    while True:
        raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        code = f"{raw[:3]}-{raw[3:]}"
        if code not in taken:
            return code


def _normalize_code(code: str) -> str:
    raw = "".join(ch for ch in code.upper() if ch.isalnum())
    return f"{raw[:3]}-{raw[3:]}" if len(raw) == 6 else code.upper()


def _clean_name(name: str) -> str:
    printable = "".join(ch for ch in str(name) if ch.isprintable()).strip()
    return printable[:MAX_DEVICE_NAME] or "Unnamed TV"
