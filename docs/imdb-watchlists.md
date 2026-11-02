# IMDb watchlists

Radarr can import a supported public IMDb movie watchlist using its native import-list configuration. TV series need the optional local bridge in `studio/imdb-watchlists.py`, which reads configured IMDb watchlists and publishes Sonarr-compatible TVDB IDs on loopback. The bridge queries IMDb, Sonarr and, when needed, TVMaze. Availability and matching depend on those upstream services; unresolved titles are reported privately. Keep personal list identifiers, titles, API keys and snapshots out of Git.

## Configure and verify

Start on the existing native host with Sonarr running, its private `state/sonarr/config.xml` in the runtime root, Python 3, and IMDb watchlists accessible to the upstream API. Copy the helper into `~/.local/share/media-server/imdb-watchlists.py`. Create `~/.local/share/media-server/state/imdb-watchlists.json` privately, replacing placeholders with your own values:

```json
{
  "port": 8765,
  "refreshSeconds": 3600,
  "lists": [{"userId": "YOUR_IMDB_USER_ID"}],
  "tvdbOverrides": {}
}
```

Choose an unused loopback port and restrict the file to the runtime owner. Optional `tvdbOverrides` maps an IMDb title ID to its TVDB series ID when automatic matching is wrong or unavailable. The supervisor starts the bridge when this file exists and Sonarr is not held or being stopped; deploy the updated controller and helper together using the installation procedure, then deliberately restart the supervisor when appropriate. Until then, the source change alone does not alter the runtime.

In Sonarr, open Settings → Import Lists, add a Custom List and set its URL to `http://127.0.0.1:PORT/YOUR_IMDB_USER_ID.json`, using your configured port and user ID. Configure movie watchlists separately in Radarr using its native IMDb list integration. Set monitoring, root folder and quality profile deliberately in each application. Check the private bridge status under `checks/imdb-watchlists/status.json`, inspect unresolved titles, and verify Sonarr receives the expected series before enabling automatic additions. A failed refresh retains the last successful feed; an initial failure returns no feed. Remove the private bridge configuration to stop supervisory launch, then inspect status to confirm. Do not publish the status, feed, API key or real identifiers.
