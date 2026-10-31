"""fetchd: the Fetch gateway, and the admin commands that pair and revoke TVs.

    python3 -m fetchd serve --port 28700
    python3 -m fetchd pending            pairing requests waiting for approval
    python3 -m fetchd approve ABC-123    approve the code a TV shows
    python3 -m fetchd devices            paired TVs
    python3 -m fetchd revoke 1a2b3c4d    unpair a TV; its token stops working at once
    python3 -m fetchd search-missing     search Radarr and Sonarr for everything still missing (cron, weekly)
    python3 -m fetchd replace-dead       replace downloads stuck for a day with another copy (cron, hourly)
    python3 -m fetchd setup-profiles     make the Up to 1080p profile and refuse disc images (once)

By default the API keys come from Radarr's and Sonarr's own config.xml, and the Plex token from Plex's
Preferences.xml. Show suggestions use a TMDB
key in <data>/tmdb.key (owner-only) when it exists. For tests, FETCHD_RADARR_URL
with FETCHD_RADARR_KEY (and the same for SONARR) point the gateway at other servers.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

from .api.devices import Registry, UnknownCode
from .arr.episodes import Episodes
from .arr.guide import EpisodeGuide
from .tmdb.show_discovery import ShowDiscovery
from .api.storage import Storage
from .jobs.stuck import StuckDownloads
from .tmdb.client import Tmdb
from .arr.library import Films, Shows
from .tmdb.browse import Browse
from .tmdb.details import Details
from .tmdb.people import People
from .tmdb.spelling import Spelling
from .jobs.missing import search_missing
from .jobs.profiles import QualityProfiles
from .api.server import Gateway, GatewayServer
from .upstream import Upstream
from .plex.watching import DEFAULT_PREFERENCES, Plex, Watching

DEFAULT_DATA = Path.home() / ".config" / "fetchd"
DEFAULT_RADARR_CONFIG = Path.home() / ".config" / "Radarr" / "config.xml"
DEFAULT_SONARR_CONFIG = Path.home() / ".config" / "Sonarr" / "config.xml"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    os.umask(0o077)
    registry = Registry(args.data / "devices.json")
    return COMMANDS[args.command](args, registry)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fetchd", description="Fetch gateway for Radarr and Sonarr")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="where paired devices are kept")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="run the gateway")
    serve.add_argument("--port", type=int, required=True)
    serve.add_argument("--host", default="127.0.0.1", help="loopback only")
    _add_config_options(serve)
    serve.add_argument("--radarr-root", default="", help="root folder for films (default: Radarr's first)")
    serve.add_argument("--sonarr-root", default="", help="root folder for shows (default: Sonarr's first)")
    serve.add_argument("--radarr-profile", default="", help="default quality profile name for films")
    serve.add_argument("--sonarr-profile", default="", help="default quality profile name for shows")
    serve.add_argument("--plex-url", default="", help="Plex on this machine, e.g. http://127.0.0.1:32400")
    serve.add_argument("--plex-preferences", type=Path, default=DEFAULT_PREFERENCES)

    commands.add_parser("pending", help="list pairing requests")
    approve = commands.add_parser("approve", help="approve a pairing code")
    approve.add_argument("code")
    commands.add_parser("devices", help="list paired devices")
    revoke = commands.add_parser("revoke", help="unpair a device")
    revoke.add_argument("device_id")
    _add_config_options(commands.add_parser("search-missing", help="search for everything still missing"))
    _add_config_options(commands.add_parser("replace-dead", help="replace downloads stuck for a day"))
    _add_config_options(commands.add_parser("setup-profiles", help="make Up to 1080p and refuse disc images"))
    return parser


def _add_config_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--radarr-config", type=Path, default=DEFAULT_RADARR_CONFIG)
    parser.add_argument("--sonarr-config", type=Path, default=DEFAULT_SONARR_CONFIG)


def _serve(args: argparse.Namespace, registry: Registry) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    radarr, sonarr = _apps(args)
    films = Films(radarr, args.radarr_root, args.radarr_profile)
    shows = Shows(sonarr, args.sonarr_root, args.sonarr_profile)
    tmdb = Tmdb(args.data / "tmdb.key")
    gateway = Gateway(registry, films, shows, Episodes(shows, EpisodeGuide()), ShowDiscovery(shows, tmdb),
                      Storage(Path.home()), People(films, shows, tmdb), Spelling(args.data / "titles.sqlite"),
                      Browse(films, shows, tmdb), Details(tmdb),
                      Watching(Plex(args.plex_url, args.plex_preferences), tmdb))
    gateway.spelling.refresh_in_background()
    server = GatewayServer((args.host, args.port), gateway)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    logging.getLogger("fetchd").info("listening on %s:%d (Radarr %s, Sonarr %s)",
                                     args.host, args.port, radarr.base_url, sonarr.base_url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def _upstream(name: str, env_prefix: str, config_xml: Path) -> Upstream:
    url, key = os.environ.get(env_prefix + "_URL", ""), os.environ.get(env_prefix + "_KEY", "")
    if url and key:
        return Upstream(name, url.rstrip("/"), key)
    return Upstream.from_config_xml(name, config_xml)


def _pending(args: argparse.Namespace, registry: Registry) -> int:
    waiting = [p for p in registry.pending() if not p["approved"]]
    if not waiting:
        print("No TV is waiting to pair. Open Fetch on the TV first.")
        return 0
    for entry in waiting:
        print(f"{entry['code']}  {entry['device']}  ({entry['age'] // 60} min ago)")
    return 0


def _approve(args: argparse.Namespace, registry: Registry) -> int:
    try:
        device = registry.approve(args.code)
    except UnknownCode:
        print(f"No TV is waiting with code {args.code}. Codes expire after 10 minutes.", file=sys.stderr)
        return 1
    print(f"Approved {device}. The TV finishes pairing within a few seconds.")
    return 0


def _devices(args: argparse.Namespace, registry: Registry) -> int:
    devices = registry.devices()
    if not devices:
        print("No TV is paired.")
    for device in devices:
        print(f"{device['id']}  {device['name']}  paired {_date(device['created'])}, last seen {_date(device['lastSeen'])}")
    return 0


def _revoke(args: argparse.Namespace, registry: Registry) -> int:
    if registry.revoke(args.device_id):
        print(f"Revoked {args.device_id}.")
        return 0
    print(f"No paired device has id {args.device_id}.", file=sys.stderr)
    return 1


def _search_missing(args: argparse.Namespace, registry: Registry) -> int:
    radarr, sonarr = _apps(args)
    search_missing(radarr, sonarr)
    print(f"{datetime.now():%Y-%m-%d %H:%M} searching Radarr and Sonarr for everything missing")
    return 0


def _replace_dead(args: argparse.Namespace, registry: Registry) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    StuckDownloads(_apps(args), args.data / "stalled.json").replace_dead()
    return 0


def _setup_profiles(args: argparse.Namespace, registry: Registry) -> int:
    for app in _apps(args):
        changes = QualityProfiles(app, args.data / "backup").set_up()
        print("\n".join(changes) if changes else f"{app.name}: nothing to change")
    print(f"Profiles that changed were saved to {args.data / 'backup'} first.")
    return 0


def _apps(args: argparse.Namespace) -> list[Upstream]:
    return [_upstream("Radarr", "FETCHD_RADARR", args.radarr_config),
            _upstream("Sonarr", "FETCHD_SONARR", args.sonarr_config)]


def _date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


COMMANDS = {"serve": _serve, "pending": _pending, "approve": _approve, "devices": _devices, "revoke": _revoke,
            "search-missing": _search_missing, "replace-dead": _replace_dead, "setup-profiles": _setup_profiles}

if __name__ == "__main__":
    sys.exit(main())
