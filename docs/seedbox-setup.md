# Seedbox setup

This guide builds the library Rated Arr talks to: Sonarr, Radarr, Prowlarr, a downloader and Plex on a
shared seedbox, wired so that adding a title is the only thing you do. Then it installs the Rated Arr
gateway next to them. It was written on [Whatbox](https://whatbox.ca); any host whose control panel
installs the same apps works the same way, though the panel steps differ.

Plan about two hours the first time. You need to be comfortable in a web UI; a little terminal helps.

```
Indexers ──► Prowlarr ──► Sonarr / Radarr ──► qBittorrent or SABnzbd ──► ~/media ──► Plex ──► your TV
              (search)      (what you want)     (downloads)                 (library)
```

You add a title in Sonarr or Radarr (or in Rated Arr on the TV). It searches through Prowlarr, hands the
release to the downloader, imports the finished file into `~/media`, and Plex shows it.

Use the stack only for media you have the right to download.

## 1. Accounts

| Account | Needed | Notes |
|---|---|---|
| A seedbox | Yes | An always-on Linux server that runs the apps and holds the library. Look at storage (1 TB or more is comfortable) and monthly bandwidth. Whatbox, Ultra.cc and similar hosts install the apps from a control panel. |
| Plex | Yes | A free account at plex.tv. You claim the server in step 2. |
| Indexers | Yes | Where searches go: Usenet indexers, private trackers or public ones (step 9). |
| A Usenet provider | No | Only if you use Usenet (step 14). |

## 2. Install the apps

From the seedbox's control panel, install qBittorrent, Sonarr, Radarr, Prowlarr and Plex. Each starts by
itself. Claim Plex through the panel's link or claim code while signed in to your Plex account, so the
server belongs to you.

Sonarr looks after TV, Radarr films, Prowlarr is the search both share, qBittorrent downloads, and Plex is
the library and player. Day to day you only touch Sonarr and Radarr, or Rated Arr.

## 3. Ports and API keys

The apps reach each other by port and API key. Find them either way:

- In each app: Settings, General shows the API key; the port is in the address bar.
- Over SSH: `~/.config/Sonarr/config.xml`, `~/.config/Radarr/config.xml` and `~/.config/Prowlarr/config.xml`
  each have `<Port>` and `<ApiKey>`; `~/.config/qBittorrent/qBittorrent.conf` has `WebUI\Port`.

Keep them in a password manager. The Rated Arr gateway reads them from those files itself, so they never
leave the seedbox.

## 4. Folders

```
mkdir -p ~/downloads ~/media/movies ~/media/tv
```

| Folder | For |
|---|---|
| `~/downloads` | Finished downloads |
| `~/media/movies` | Radarr's library and Plex's Movies |
| `~/media/tv` | Sonarr's library and Plex's TV Shows |

With downloads and media on the same disk, Sonarr and Radarr import by hardlink: the file appears in the
library without a second copy.

## 5. Passwords on every app

The apps listen on ports anyone can reach. Before anything else:

- Sonarr, Radarr and Prowlarr: Settings, General, Security. Authentication Forms (Login Page),
  Authentication Required Enabled, a username and a strong, unique password.
- qBittorrent: Tools, Options, Web UI. A strong password, never your seedbox account's.
- Open the apps through the host's HTTPS links, not `http://host:port`, which sends passwords in clear.

API keys bypass the login page, so the next steps keep working with passwords set.

## 6. qBittorrent

Tools, Options, Downloads: Default Save Path `/home/<you>/downloads`. Under BitTorrent, set seeding limits
that fit your trackers' rules and your plan's bandwidth. Private trackers usually expect a ratio; with
public ones you can pause torrents as soon as they finish.

## 7. Sonarr and Radarr

In both apps:

1. Settings, Download Clients, add qBittorrent: host `127.0.0.1`, its Web UI port, username and password.
   Test, then Save. Leave Completed Download Handling on.
2. Settings, Media Management, Root Folders: `/home/<you>/media/tv` in Sonarr, `/home/<you>/media/movies`
   in Radarr.

Quality profiles come in step 12: `tools/setup-profiles` adds **Up to 1080p** to both apps. It takes
anything from SD to 1080p, so old titles that only exist in SD are found, and upgrades until a WEB 1080p
copy arrives. It takes no 4K, remuxes or disc images. It also stops every profile taking disc images
(BR-DISK): those are whole Blu-ray `.iso` files that Plex cannot play or list.

## 8. Prowlarr

Settings, Apps: add Sonarr, then Radarr. Prowlarr Server `http://127.0.0.1:<prowlarr port>`, the app's
server `http://127.0.0.1:<its port>`, its API key, Sync Level Full Sync. Test, then Save. Indexers you
add in Prowlarr now reach both apps.

## 9. Indexers

In Prowlarr, Indexers, Add Indexer: pick the indexers you have access to, give a private tracker or Usenet
indexer its credentials or API key, Test, Save. Add a few so searches have coverage.

Prowlarr sends a film indexer only to Radarr and a TV indexer only to Sonarr, so the two can list different
counts.

## 10. Plex

1. Settings, Libraries, Add Library: Movies on `/home/<you>/media/movies`, TV Shows on
   `/home/<you>/media/tv`, with Plex's default agents.
2. In Sonarr and Radarr: Settings, Connect, add Plex Media Server on `127.0.0.1` and Plex's port, sign in,
   turn Update Library on. The library then rescans when something imports.

Plex's port is usually 32400, but seedboxes often move it. Check which port answers
(`curl http://127.0.0.1:<port>/identity`) before you use it.

## 11. Test end to end

In Radarr, Add New, pick a well-known film, choose the root folder, tick Start search and add it. Activity,
Queue shows the grab; when the download finishes, Radarr imports it and it appears in Plex. If nothing is
found, the cause is almost always indexer coverage, not the wiring.

## 12. The Rated Arr gateway

The gateway (`fetchd`) is a small Python service, standard library only, that the TV app talks to. It
listens on `127.0.0.1` and is reached through the host's HTTPS proxy.

1. **An HTTPS address.** On Whatbox, the Domain page maps a name such as `fetch.<you>.box.ca` to a port.
   Pick a free port for the gateway and point a domain at it.
2. **Settings.** On your computer, `cp fetch.properties.example fetch.properties` and fill in that address,
   your SSH login (key login, no password prompts), the gateway's port and Plex's port.
3. **Deploy.** `tools/deploy-gateway.sh` copies the gateway to `~/fetch` and adds cron entries: start it at
   boot and every 5 minutes if it stopped, replace downloads stuck for a day (hourly), and search for
   everything still missing (Sundays at 04:40). `tools/deploy-gateway.sh --remove` takes it all away again.
4. **Quality profiles.** `tools/setup-profiles` (step 7). It saves each profile it changes to
   `~/.config/fetchd/backup` first; running it again changes nothing.
5. **TMDB (optional).** For show suggestions, people search and title details, put a
   [TMDB API key](https://www.themoviedb.org/settings/api) in `~/.config/fetchd/tmdb.key` (owner-only,
   `chmod 600`). The gateway reads it on each use.

Pair the TV as the [README](../README.md#install-the-app-and-pair-the-tv) describes.

## 13. Watch on the TV

Install Plex on the TV and sign in with the account that owns the server. A seedbox is never on your home
network, so every stream counts as remote: since April 2025 that needs Plex Pass on the server owner's
account, or a Remote Watch Pass per viewer. Jellyfin is a free alternative with the same wiring.

## 14. Usenet

Usenet downloads over an encrypted connection from your provider's servers, with nothing to seed. You need
a provider (server access), an indexer (search) and a newsreader:

1. Install SABnzbd from the panel and give it your provider's server, SSL port, username and password.
2. In Sonarr and Radarr: Settings, Download Clients, add SABnzbd with its host, port and API key. It runs
   next to qBittorrent; the apps pick the best release.
3. In Prowlarr, add the Usenet indexer with its API key. Full Sync passes it to both apps.

Keep your passwords, API keys and Plex token in a password manager, never in a copy of this guide.
