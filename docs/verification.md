# Verification and known limits

[Home](../README.md) · [Operation](operations.md) · [Migration](migration.md)

## Automated checks

From the repository root, with Python 3.11+:

```sh
python3 -m unittest discover -s studio -p 'test_*.py'
```

The current suite has 55 checks covering disk identity/mount/marker/path failures, registration rollback, Bonjour changes, ordinary-user boot configuration, log rotation, preserved catalog history/authentication, full Torznab URL paths, collection roots, stopped torrents, database backup integrity and bounded one-time transfer-preference conversion, import-safe seeding actions, boot-only activation, library identity refresh after renaming and protected torrent identities alongside legitimate new downloads, explicit owner cleanup and private-network proxy policy generation. They also reject mismatched loaded boot jobs, preserve maintenance on startup failure, require stopped apps and complete native settings for rebuilds, serialize backup writers, discard stale partial snapshots and exclude regenerable cover artwork without removing live files. Retention uses completion time, and manual snapshots satisfy the daily schedule. Recorded owner-requested re-downloads can reuse deleted hashes; unexplained reappearances still fail.

These use temporary fixtures and mocks. They do not mount a real disk, start applications or establish that a cloud-protected provider is currently available.

## Live qualification on 15 October 2026

Observed on an M1 Max Studio with 32 GiB memory and ten CPU cores:

- System-domain supervisor running as the ordinary owner; no Aqua/login restriction in the boot job. All seven service endpoints healthy.
- All 13 configured Arr indexer entries passed real provider search/connection tests, and both qBittorrent client connections passed and were enabled.
- FlareSolverr launched its ARM64 managed browser/driver and solved real provider challenges. The driver required local signing after its upstream binary patch.
- Bazarr's native Arr event connections and scheduled jobs active; restored subtitle providers reported healthy. Jellyfin is named Mac Studio, its Movies/TV Shows libraries resolve their IDs/options after a scan, and library monitoring is enabled. Original Sonarr/Radarr user rows exactly match the restored source databases.
- Forced Jellyfin playback produced a valid 720p H.264/AAC segment; its actual FFmpeg log confirmed VideoToolbox hardware decode and encoding.
- A controlled unavailable-UUID test stopped all seven services and closed Caddy/app/Solver ports. Restoring the real profile recovered services with new PIDs, aliases and routing.
- All six `.local` names resolved and returned expected HTTP responses from another LAN computer. Authenticated application checks through Caddy passed before the owner selected password-free home management. The current five management pages are qualified without browser credentials; Jellyfin keeps its account.
- The five password-free management routes passed fresh-cookie, no-credential checks from another LAN computer. Direct management ports refused LAN connections; all five listeners were loopback-only. An isolated Caddy check rejected an out-of-range peer, including spoofed forwarding headers. Jellyfin stayed running during management reconfiguration.
- qBittorrent now stops at the seeding limit instead of removing completed torrents before Arr can import them. The old speed and ratio limits remain.
- Native settings snapshots completed; six copied SQLite databases independently passed full integrity checks. The retained imported queue was initially verified stopped without transfers. The owner subsequently deleted those entries; this intentional cleanup is recorded privately and is not reversed.

Raw receipts, tokens, private database copies, exact household inventories and logs remain on the runtime host. This document summarizes observations without publishing that material.

## Performance

In three short idle samples, the entire media process tree used about 1.6 GiB summed resident memory and 0.2% of one CPU core. Summed RSS is approximate and can count shared pages more than once. The whole Studio was about 70–72% CPU idle with about 8.3 GiB unused RAM; no swap I/O occurred during the short system sample.

These are idle observations, not resource limits or a capacity guarantee. Scans, subtitle work and Solver challenges create temporary bursts. Hardware playback is verified, but sustained transcode load and simultaneous-stream capacity were not measured. AI work and playback share the host's memory/resources.

## Remaining limits

- A fresh cold boot without graphical login, actual physical drive disconnection and Apple TV/iPad playback remain unobserved. Do not reboot/log out unrelated workloads solely to manufacture evidence.
- Provider availability changes; an installed/running Solver does not guarantee a future challenge can be solved. Re-test actual searches after provider/browser changes.
- The importer expects the deployment's five retained torrent records. `verify` protects their imported hashes and stopped resume flags while allowing unrelated new downloads. Older receipts derive identities from the restored original queue; keep that source until the receipt has been deliberately upgraded. Explicit owner removal decisions are recorded separately by hash in private `checks/removed-torrents.json`; unexplained missing records still fail verification.
- Radarr retains a catalog notice for titles removed from TMDb. Records were preserved rather than deleted to hide an external metadata warning.
- Settings backups are individually consistent per SQLite database and reside on the media disk. They are not a cross-application transaction, an independent copy of the media or offsite protection.
- Rebuilds require private native backups and compatible applications. Only the existing deployment and listed checks are qualified; a blank-machine installation is not claimed.
