"""How much of the plan's disk space is used, the way Whatbox's own page shows it.

Whatbox limits each user with an XFS user quota, so the numbers come from `xfs_quota` for the disk
that holds the home folder. Without quotas (a test machine) it falls back to the disk's own free space.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

CACHE_SECONDS = 60
XFS_QUOTA = "/usr/bin/xfs_quota"


class Storage:
    def __init__(self, home: Path, run: Callable[[list[str]], str] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.home = home
        self.run = run or _run
        self.clock = clock
        self._lock = threading.Lock()
        self._cache: tuple[float, dict] | None = None

    def usage(self) -> dict:
        """{"used", "limit", "free"} in bytes, and "source": "quota" or "disk"."""
        with self._lock:
            if self._cache and self.clock() - self._cache[0] < CACHE_SECONDS:
                return self._cache[1]
            usage = self._quota() or self._disk()
            self._cache = (self.clock(), usage)
            return usage

    def _quota(self) -> dict | None:
        mount = mount_point(self.home)
        try:
            output = self.run([XFS_QUOTA, "-c", "quota -u -b -N", mount])
        except (OSError, subprocess.SubprocessError):
            return None
        return parse_quota(output)

    def _disk(self) -> dict:
        disk = shutil.disk_usage(self.home)
        return {"used": disk.used, "limit": disk.total, "free": disk.free, "source": "disk"}


def parse_quota(output: str) -> dict | None:
    """The first line of `quota -u -b -N`: device, used, soft quota, hard limit, all in KiB."""
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 4 and all(f.isdigit() for f in fields[1:4]):
            used, soft, hard = (int(f) * 1024 for f in fields[1:4])
            limit = hard or soft
            if limit <= 0:
                return None
            return {"used": used, "limit": limit, "free": max(0, limit - used), "source": "quota"}
    return None


def mount_point(path: Path) -> str:
    """The mount point of the filesystem holding path, following symlinks (Whatbox homes are links)."""
    current = os.path.realpath(path)
    while not os.path.ismount(current):
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return current


def _run(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, timeout=10, check=True).stdout
