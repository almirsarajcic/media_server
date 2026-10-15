# Downloads appearing in Jellyfin

[Home](../README.md) · [Operation](operations.md) · [English subtitles](subtitles.md)

The acquisition path is qBittorrent completion → Radarr/Sonarr successful library import → native Jellyfin path-update notification. Jellyfin folder monitoring remains enabled as another discovery mechanism. Downloads still waiting in the download directory are not library imports.

## Configuration and ownership

Both Arr apps have a native **Emby / Jellyfin** connection named **Jellyfin library update**. It uses `127.0.0.1:8096`, HTTP, empty URL base and path mappings, and a dedicated Jellyfin API key named **Media import updates**. Import/download, upgrade, rename and supported deletion events are enabled. **Update Library** is enabled; **Send Notifications** is disabled because that Emby feature is unsupported by Jellyfin. No extra worker or service is involved. The native app databases own these settings; private backups preserve them.

Radarr's native **Kodi (XBMC) / XbmcMetadata** configuration named **Jellyfin movie identity** writes `movie.nfo` with provider IDs. Movie metadata and the `movie.nfo` filename are enabled; movie images are disabled so Jellyfin continues to own artwork. Radarr owns these NFO files. This lets new imports carry their exact identity instead of relying solely on title/year matching. Existing library paths and video filenames remain stable.

## Verify or repair

Inputs: healthy local services, completed library import, the dedicated API key and a path shared identically by Arr/Jellyfin. Start in the apps' Settings → Connect and Jellyfin Dashboard → API Keys. Preserve existing connection settings before replacing them.

1. Check Radarr/Sonarr's movie/episode file and queue. Require a real readable file under the registered `media/movies` or `media/tv` library. Import warnings need their own repair before a Jellyfin refresh can help.
2. Test each native connection. If recreating it, use the settings above and keep the API key private. Keys/tokens in query strings or obsolete headers may fail on this Jellyfin version: the native connector sends `Authorization: MediaBrowser Token="…"` and `X-MediaBrowser-Token`.
3. Verify the actual update protocol, rather than relying solely on the connection test: authenticated `POST /Library/Media/Updated` with `Updates` containing the imported library path and `UpdateType=Created`. HTTP 204 was observed using the native connector's exact header format.
4. Confirm the item appears for the intended Jellyfin user, its path exists, and its TMDb/IMDb IDs match Radarr. If the wrong same-title film appears, use Jellyfin Identify with Radarr's exact provider ID. A library scan alone cannot correct a previously wrong identity reliably.
5. Check the native `movie.nfo` IDs. For an existing title, Radarr's targeted movie refresh generates its metadata without another download. Reopen/refresh the client library after the corrected metadata is visible server-side.

Outputs are saved connections, native NFO metadata and Jellyfin's refreshed item. On failure, inspect Arr's connection errors and Jellyfin's logs, check the live API key and shared paths, then retest the authenticated path update. Preserve prior configurations for rollback. Do not restart the full stack just to refresh a movie, and do not fabricate a download event or start another torrent as a test.

## Qualification

Both native connections and the exact authenticated path-update request passed on 15 October 2026. A real imported movie was corrected to Radarr's exact provider identity and verified with its native NFO metadata. Future real download-to-callback execution is configured but has not yet been observed after enabling these connections.

Bazarr automatically assigned the English profile and downloaded English subtitles for that new import. Exact titles, IDs, timestamps, before-change settings and credentials remain in private Studio receipts.

References: [Jellyfin folder monitoring](https://jellyfin.org/docs/general/administration/troubleshooting.html/#real-time-monitoring), [local NFO metadata](https://jellyfin.org/docs/general/server/metadata/nfo/), [Radarr native library-update implementation](https://github.com/Radarr/Radarr/blob/develop/src/NzbDrone.Core/Notifications/MediaBrowser/MediaBrowserProxy.cs).
