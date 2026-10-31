# Set up the seedbox with an AI coding agent

The [seedbox guide](seedbox-setup.md) by hand takes about two hours. An AI coding agent with SSH access
(Claude Code, for example) can do most of it over the apps' APIs while you watch. Replace the `<...>`
placeholders in the first paragraph, paste everything below the line into the agent, and answer when it
stops. It pauses only where it needs you: adding indexers, and getting a Plex token if none is stored.

---

I have a shared seedbox at **`<HOST>`** reachable via **`ssh <USER>@<HOST>`** (key auth already set up).
No root, no Docker; everything lives in my home directory. Installed and running through the host's
control panel: **qBittorrent, Sonarr, Radarr, Prowlarr and Plex** (Plex already claimed to my account).

Wire the whole pipeline together over SSH. Do everything you can through the apps' APIs, **explain each
change before you make it**, and stop for me only where you must.

## What to do

1. **Discover** each app's port and API key by reading its config over SSH:
   - Sonarr, Radarr, Prowlarr: `~/.config/<App>/config.xml`, `<Port>` and `<ApiKey>`.
   - qBittorrent: `~/.config/qBittorrent/qBittorrent.conf`, `WebUI\Port` and the username.
   - Check each API answers before continuing. **Call every API from localhost over the SSH session**
     (`curl 127.0.0.1:<port>`), never the public interface.
2. **Folders:** create `~/downloads`, `~/media/movies` and `~/media/tv`. Set qBittorrent's default save
   path to `~/downloads` through its API.
3. **Sonarr and Radarr:**
   - Add qBittorrent as the download client and **test** the connection.
   - Root folder `~/media/tv` for Sonarr, `~/media/movies` for Radarr.
   - Turn on Completed Download Handling.
4. **Prowlarr:** add Sonarr and Radarr as Applications with **Full Sync**, so any indexer I add in
   Prowlarr reaches both.
5. **Security, required:** turn on Forms authentication with a strong, **generated** password on Sonarr,
   Radarr and Prowlarr, and a strong Web UI password on qBittorrent (not the default, not my account
   password). These sit on a public server. **Generate the passwords and show them to me once** so I can
   save them.
6. **Plex:** add a Plex Media Server connection in Sonarr and Radarr (Settings, Connect) so libraries
   refresh on import. Get a Plex token: read it from Plex's config if it is there, otherwise walk me through
   getting one. Check the Plex libraries point at `~/media/movies` and `~/media/tv`; create the Movies and
   TV Shows libraries if they are missing, or tell me exactly what to click.
7. **Indexers:** tell me what to add in Prowlarr's UI and **pause** while I add the indexers I have
   access to. When I say "done", check that Full Sync reached both apps.
8. **End-to-end test:** add one well-known film in Radarr through the API, confirm Prowlarr finds a
   release, qBittorrent downloads it, Radarr imports it to `~/media/movies` and it appears in Plex. Then
   walk me through checking it on my TV.
9. **Rated Arr:** follow step 12 of `docs/seedbox-setup.md` in the rated-arr repository: an HTTPS domain for
   the gateway, `fetch.properties`, `tools/deploy-gateway.sh`, then `tools/setup-profiles` for the
   Up to 1080p profile.

## Rules

- Explain each change before making it. **Change nothing outside my home directory.** If an API call
  fails, **show me the error before retrying**.
- This is a shared server: keep secrets off the process list. Write them to a mode `600` file in my home
  directory and read them from there; never pass passwords as command-line arguments.
- My level: comfortable in a terminal, new to Sonarr, Radarr and Prowlarr. Explain their ideas as you go.

## Things that cost time

- Sonarr, Radarr and Prowlarr API calls authenticate with the `X-Api-Key` header and **skip the Forms
  login**, so you can configure them before or after setting passwords. Prowlarr reaches the apps with the
  same key, so the passwords do not break sync.
- `/config/host` and similar PUT endpoints reject partial bodies: **GET the whole object, change it, PUT it
  back.** Expect `202` on success.
- **qBittorrent:** its Web UI answers **403 Forbidden** (not 401) when unauthenticated; requests need a
  **`Referer` header** matching its base URL; and `WebUI\LocalHostAuth=true` means login is **required even
  on localhost**. Log in with `POST /api/v2/auth/login` (HTTP 200 or 204 and a `SID` cookie), set the new
  password with `POST /api/v2/app/setPreferences` and `{"web_ui_password":"..."}`, then log in again to
  check the new one works and the old one fails.
- Python's default cookie jar does not keep cookies for a bare IP host; read the `Set-Cookie` header
  directly.
- **Plex's local API may not be on 32400**: seedboxes often move it, so probe for the real port. The server
  token is `PlexOnlineToken` in `~/Library/Application Support/Plex Media Server/Preferences.xml`.
- Prowlarr sends a film-only indexer to Radarr and a TV-only one to Sonarr, so their counts can differ.
- If qBittorrent's old Web UI password was the same as my seedbox password, tell me to **change my seedbox
  password** afterwards.

## Once it works, offer these (do not do them without asking)

- A qBittorrent **seeding policy** that fits my trackers' rules and my plan's bandwidth, with the trade-off
  for private trackers, which expect a ratio.
- The **Plex remote streaming paywall**: the server is in a datacenter, so all playback counts as remote and
  needs Plex Pass on the owner's account or a Remote Watch Pass per viewer. Mention **Jellyfin** as the free
  alternative.
- **Usenet** as a second download path: a provider (a tier-one one rather than a reseller), an NZB indexer,
  and SABnzbd or NZBGet next to qBittorrent.
