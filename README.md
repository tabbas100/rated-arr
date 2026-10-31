# Rated Arr

An Android TV app for finding films and shows and adding them to Radarr and Sonarr on your seedbox, from
the sofa with the remote. A small gateway runs on the seedbox next to them; the TV talks only to that and
never holds a Radarr, Sonarr, Plex or TMDB key. Its look is a 70s grindhouse poster for so-bad-it's-good
nights. The code calls it Fetch.

- **Search** films, shows and people: "seagal" lists his films and shows. A typo still finds the title:
  "glimer man" finds The Glimmer Man.
- **Browse** by genre, with "So bad it's good" first for films, plus suggestions for shows.
- **Title pages** with tagline, director or creators, rating and cast; an actor opens a search.
- **Add** a film, or a show with all, the latest, the first or only future seasons, or exactly the episodes
  you pick.
- **Downloads** with progress and a plain-words reason when one is stuck.
- **Library**: what takes the most space and how much is left, and deletes that always ask first.
- **Continue watching**: Plex's Continue Watching copied into the TV's Watch Next list, where any home
  screen that reads the list can show it; Plex itself tells only Google TV's own home screen. A home
  screen can ask for fresh rows with an explicit broadcast to
  `com.androidtv.fetch/.watchnext.WatchNextRefresh`, and a row opens the film or episode in Plex with
  Resume focused.

On the seedbox the gateway also replaces downloads that have been stuck for a day, searches once a week
for everything still missing, and can set up a sensible quality profile.

Use it only for media you have the right to download.

## How it works

```
TV app ──HTTPS (pinned)──► host's HTTPS proxy ──► fetchd on 127.0.0.1 ──► Radarr, Sonarr, Plex (localhost)
  device token sealed in                          search, add, episodes,    TMDB (suggestions, people,
  the Android Keystore                            downloads, library        details, typo fixing)
```

- **The TV holds one secret:** a device token, sealed with a key in the Android Keystore. The app makes no
  backups, allows HTTPS only, trusts system certificate authorities only, and for Whatbox hosts (`*.box.ca`)
  pins the issuing roots (`app/src/main/res/xml/network_security_config.xml`).
- **Pairing is approved over SSH.** The TV shows a code; `tools/pair` on your computer confirms it over your
  SSH key, so only someone who can log in to the seedbox can pair a TV. The gateway stores only hashes of
  tokens. `tools/pair revoke` unpairs a TV at once.
- **Keys stay where they are.** The gateway reads Radarr's and Sonarr's API keys from their own
  `config.xml`, and the Plex token from Plex's `Preferences.xml`, on the seedbox. Nothing is copied.
- **The gateway** is Python 3, standard library only, and listens on `127.0.0.1` behind the host's HTTPS
  proxy. It refuses browser requests, limits failed logins and pairing attempts, and a delete needs an
  explicit `"confirm": "delete"` in the request.

## Set up the seedbox

[docs/seedbox-setup.md](docs/seedbox-setup.md) builds the whole library on a seedbox, step by step: Sonarr,
Radarr, Prowlarr, qBittorrent or SABnzbd, Plex, then this gateway. To let an AI coding agent do it over SSH
instead, use [docs/agent-setup.md](docs/agent-setup.md). It was built on [Whatbox](https://whatbox.ca);
other hosts work with their own panel steps.

The short version, once Sonarr, Radarr and Plex run:

```
cp fetch.properties.example fetch.properties   # your gateway address, SSH login and ports
tools/deploy-gateway.sh                         # install the gateway and its cron entries
tools/setup-profiles                            # the "Up to 1080p" quality profile, no disc images
```

## Install the app and pair the TV

You need JDK 17 and the Android SDK (platform 34). The TV must run Android TV or Google TV 9 or later with
ADB debugging on.

1. **A release key.** `tools/release-key.sh` makes `~/.android-keys/fetch-release.jks` and keeps its
   password in the macOS Keychain. On another system, change `signingConfigs` in `app/build.gradle`. Back
   the key up: an update signed with another key needs an uninstall and a new pairing.
2. **Build.** `sh ./gradlew assembleRelease`. The gateway address comes from `fetch.properties`.
3. **Install.** `adb install -r app/build/outputs/apk/release/app-release.apk`.
4. **Pair.** Open Rated Arr on the TV; it shows a code. Run `tools/pair` and type the code.

## Everyday commands

| Task | Command |
|---|---|
| Pair a TV | `tools/pair` |
| List paired TVs | `tools/pair devices` |
| Unpair a TV | `tools/pair revoke <id>` |
| Update the gateway | `tools/deploy-gateway.sh` |
| Remove the gateway and its cron entries | `tools/deploy-gateway.sh --remove` |
| Set up quality profiles | `tools/setup-profiles` |
| Read the gateway's log | `ssh <you>@<seedbox> tail ~/fetch/fetchd.log` |
| Redraw the banner and icon | `tools/make_art.py` (needs Pillow) |

## Where things are

| What | Where |
|---|---|
| App screens | `app/src/main/java/com/androidtv/fetch/screens/` |
| App parts: cards, tab bar, posters, dialogs, labels | `…/fetch/ui/` |
| App's gateway client and JSON | `…/fetch/gateway/` |
| What the gateway sends: titles, downloads, episodes, library | `…/fetch/model/` |
| Device token storage | `…/fetch/security/` |
| Continue watching for home screens (`WatchNextRefresh`, `ResumeActivity`) | `…/fetch/watchnext/` |
| Gateway's HTTP API, pairing, limits, disk space | `gateway/fetchd/api/` |
| Gateway's Radarr and Sonarr calls | `gateway/fetchd/arr/` |
| Gateway's cron and setup commands | `gateway/fetchd/jobs/` |
| Gateway's TMDB features | `gateway/fetchd/tmdb/` |
| Gateway's Plex Continue Watching | `gateway/fetchd/plex/` |
| Your settings | `fetch.properties` (from `fetch.properties.example`; kept out of git) |
| Paired TVs (hashes only) | seedbox `~/.config/fetchd/devices.json` |
| TMDB key (optional) | seedbox `~/.config/fetchd/tmdb.key`, owner-only; without it, suggestions, people and details are off |
| Title list for typo fixing | seedbox `~/.config/fetchd/titles.sqlite`, about 200 MB of TMDB titles, fetched again every two weeks |
| Profile backups | seedbox `~/.config/fetchd/backup/` |
| Design | [docs/ui-kit](docs/ui-kit), the look's tokens and parts |

## Defaults worth knowing

- New films and shows use the **Up to 1080p** profile when it exists, else HD-1080p, never a profile that
  takes disc images: Radarr would grab whole Blu-ray `.iso` files, which Plex cannot play or list.
- Choosing episodes makes exactly the picked ones monitored. Save stays off until something changes, so
  opening the picker never rewrites a show.
- Every delete asks first, with Cancel focused. Deleting a film's file or some episodes also unmonitors
  them, so they are not downloaded again. Removing a title deletes its files. Each delete is logged.
- A download with no progress for 24 hours is removed, blocklisted and searched for again, except paused
  downloads and unmonitored titles.
- The Library tab's disk space comes from the XFS quota (`xfs_quota`), as Whatbox reports it.
- The certificate pins expire on 2027-10-26. Renew them before then, or the app falls back to normal
  certificate checks.

## Tests

```
cd gateway && python3 -m unittest discover -s tests -t .                       # gateway
tools/test-servers.sh up && FETCHD_IT=1 python3 -m unittest discover -s tests -t .   # + Radarr, Sonarr 3 and 4 in Docker
tools/test-servers.sh down
sh ./gradlew testReleaseUnitTest lintRelease                                  # app tests and lint (warnings fail)
```

Debug builds talk to a gateway on your own computer: `tools/local-gateway.sh` runs it against the Docker
test servers, over HTTPS with a throwaway certificate authority that `tools/test-tls.sh` creates (macOS).
Run that once before the first debug build.

## Credits

This product uses the TMDB API but is not endorsed or certified by TMDB. Each install uses its own TMDB API
key under [TMDB's terms](https://www.themoviedb.org/api-terms-of-use).

Rated Arr is not affiliated with Radarr, Sonarr, Prowlarr, Plex, TMDB or Whatbox.

Fonts: [Outfit](https://github.com/Outfitio/Outfit-Fonts), [Anton](https://github.com/googlefonts/AntonFont)
and [Courier Prime](https://github.com/quoteunquoteapps/CourierPrime), all under the SIL Open Font License
1.1 (the `*-FONT-OFL-1.1.txt` files).

The code is under the [MIT License](LICENSE).
