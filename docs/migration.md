# Import restored configurations

[Home](../README.md) · [Installation](installation.md) · [Operation](operations.md)

## Inputs and boundaries

Use verified local archives already restored to the external disk. Restoring files and importing them into live native applications are separate steps. The retired host is not a dependency. Disk formatting, archive transfer, household cleanup decisions and private verification manifests are deliberately not published here.

The supported layout is `/Volumes/Media/media_server/`: original `sonarr/`, `radarr/`, `bazarr/`, `jackett/` and `qbittorrent/` configurations alongside `data/{movies,tv,downloads}/`. Active native state remains on the internal SSD under `~/.local/share/media-server/state/`.

This importer is deployment-specific. It expects compatible native/source database schemas and exactly five retained torrent/resume pairs. It rejects an existing native queue or an already-recorded import. Review these assumptions before adapting it to a different collection; do not bypass a count/schema check blindly.

## Register an external volume

Inputs: verified existing media directories, a writable external volume and its actual post-format UUID. The controller does not format or transfer data. Stop the stack first and read disk identity independently with `diskutil`.

```sh
./media-server stop
./media-server storage --uuid ACTUAL_VOLUME_UUID \
  --mountpoint /Volumes/Media \
  --media-root /Volumes/Media/media_server/data
./media-server check
```

Replace the UUID placeholder with the verified value. Registration creates the stable `media` symlink, validates the gate and records the profile. The destination must not already exist; it refuses to replace any existing library directory or link. A changed disk/owner needs a reviewed profile/link migration and a native-state backup. Registration links the existing media directory; it does not copy media.

Success means the correct filesystem, exact mount, marker and required same-filesystem directories pass the gate. A failed registration rolls back the stable-path change.

## Offline import and activation

Start in the private Studio runtime with a healthy external profile and all archive checks complete.

1. Save a native settings backup, then run `./media-server stop`. Require fresh maintenance status with no application children.
2. Run `./media-server import-configs`. It makes a complete private native-state rollback snapshot before modifying live databases. Never run it against active writers.
3. Run `./media-server start` and wait for native endpoint health. Inspect `checks/config-import.json` and app logs.
4. Verify catalog counts, native authentication, existing paths and the stopped queue before enabling acquisition.
5. With Solver installed and healthy, run `./media-server acquisition`. It tests providers, enables passing indexers and download clients, restores bounded original qBittorrent preferences once, enables Bazarr scheduling and enables Jellyfin folder monitoring. A failed provider remains saved but disabled with private diagnostic evidence. Rerun this command after repairing its actual failure.
6. Rescan the restored libraries through the native application APIs/UI. Check that retained files are recognized and removed media has not been reintroduced. Run `./media-server verify` and create a fresh backup.

The output is migrated native state plus private import/acquisition receipts. Preserve the source archives and rollback snapshot until the actual applications have been qualified.

## Preserved and adapted settings

- Sonarr/Radarr databases retain catalog IDs and history. Original login rows, password hashes, salts and iteration settings are retained after a schema compatibility check; native API keys remain unchanged. Source `/data/` paths and standalone root paths are translated to the stable native media path, including collection roots.
- Jackett Torznab URLs retain their full provider path while their host/API key is adapted. The old `rarbg` route was mapped to the configured TheRARBG provider in the existing deployment; check provider availability when adapting a different archive.
- Download-client host, port and credentials point to native qBittorrent. Original categories are retained; completed-download handling remains native.
- Existing catalog records become unmonitored, indexers/clients initially disabled, and retained resume records stopped with auto-management disabled. These are import safeguards; acquisition activation is the explicit next step. New monitored entries can then use the enabled pipeline.
- The one-time qBittorrent preference import translates original KiB/s limits to the WebAPI's bytes/s values and restores explicit queue/seeding settings. Automatic removal at the seeding limit is changed to stop, so completed payloads stay available for Arr import. It preserves native authentication/storage and does not overwrite later changes on reruns.
- Bazarr's database and provider/language settings are imported while keeping native authentication and localhost Sonarr/Radarr configuration. Jackett provider records are refreshed while retaining its native server configuration.
- Plex configuration remains archived. Plex-to-Jellyfin watched-state conversion is not implemented; do not report it as migrated.

Missing torrent payloads remain missing: a stopped record is not a media backup or an instruction to re-download. Do not enable old monitoring or restart those torrents merely to clear a status warning. The Studio owner subsequently removed all five retained queue entries; leave them removed. That choice is recorded privately in `checks/removed-torrents.json` with `removed_hashes`, the decision and its provenance. For another explicitly requested cleanup, preserve the original import receipt and record only confirmed original hashes in this separate removal receipt. Never create that exception to hide an unexplained loss. A later owner-requested download can reuse the same torrent hash. Record only that verified identity in `readded_hashes`, with `readded_provenance` linking the owner request and subsequent Arr grab/import evidence. It is then treated as a new download; other deleted hashes must remain absent. Do not infer this exception merely because a record reappeared.

## Recover original Arr access

Current native backups preserve the configured authentication rows. If recovering original accounts from the source archive is necessary, make a backup, stop the stack, run `./media-server restore-logins`, then start and verify. It requires confirmed maintenance, copies compatible Sonarr/Radarr user rows from the restored source databases and preserves native API keys. Use the original Arr usernames/passwords afterward. `state/access.json` describes the other native tools.

## Failure and rollback

On an import exception, the controller restores its native-state snapshot and preserves the failed state for inspection. Keep all owned services stopped while restoring a database snapshot manually. On schema mismatch, missing archive members or an unexpected queue, inspect the exact evidence and repair inputs; do not rerun over newer native state.

Completion requires valid databases, expected IDs/counts, original Arr access and native access for the other tools, corrected paths, an intentionally stopped imported queue, real provider/client tests and a final verified settings backup.
