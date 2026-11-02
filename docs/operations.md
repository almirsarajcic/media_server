# Operate the Studio

[Home](../README.md) · [Installation](installation.md) · [Migration](migration.md) · [Verification](verification.md)

## Inputs and starting location

Use a Terminal or SSH session as the Studio runtime owner. The registered external disk, installed applications and private state must already exist. Start in `~/.local/share/media-server/`; repository copies are source, not the live runtime. Tools are Python 3.14, launchd, diskutil and the native application APIs.

The single system job is `/Library/LaunchDaemons/com.almirsarajcic.media-server.plist`. Its root-owned plist specifies the ordinary user; application code does not run as root. Kogen, Halcyon and unrelated login/startup jobs are outside this controller's ownership.

## Routine commands

```sh
./media-server status
./media-server check
./media-server stop
./media-server start
./media-server verify
./media-server backup
```

1. Inspect `status` and `check`. Healthy external operation means `job_domain=system`, `phase=running`, seven app endpoints, six Bonjour publishers, Caddy and the settings-backup worker.
2. Use `stop` before maintenance. It terminates owned process groups and confirms a persistent maintenance hold. The supervisor stays loaded, so routine stop/start does not require sudo. The hold survives a supervisor restart.
3. After maintenance, `start` checks storage, validates the installed and loaded boot job against the runtime path/owner, and releases the hold. It does not reload already-running supervisor code.
4. Run `verify` for authenticated interfaces, configured acquisition state, retained queue invariants and a real short hardware transcode. Any retained imported torrent identities must stay stopped; unrelated new downloads and recorded intentional removals are allowed. See [verification limits](verification.md).
5. Run `backup` for a fresh settings snapshot. Do not overlap maintenance, restore, backup or storage-recovery tests.

Outputs are `state/status.json`, `logs/` and private `checks/` receipts. Status marks old running, degraded, blocked or maintenance reports stale after 90 seconds. Endpoint health means HTTP availability, not a complete search/download/playback workflow.

## Update the installed controller

Inputs: a reviewed source revision, passing local tests and an existing healthy deployment. Preserve the installed controller before replacing it.

1. Copy `studio/media-server` from the checkout to runtime as `media-server.next`; make it executable and rename it atomically to `media-server`.
2. Run `./media-server stop` and wait for confirmation. Read the supervisor PID from fresh `status` output.
3. Terminate only that supervisor PID with `kill -TERM PID`. launchd replaces it; never kill arbitrary Python/application processes by name.
4. Confirm a new supervisor PID and fresh maintenance status, then run `./media-server start`.
5. Confirm system-domain health and run the appropriate verification. Do not bootstrap a second login job.

The output is the new source running under the existing system job. If replacement fails, retain maintenance, inspect supervisor logs and restore the saved controller atomically. A whole-Mac reboot is not required for this update.

## Storage and process recovery

The supervisor rechecks storage every five seconds and immediately before starting each child. It retries exited processes after 30 seconds. If an attached expected disk is unmounted, it mounts only the verified UUID and rechecks everything before proceeding. There is no automatic internal-disk fallback.

For a deliberate controlled test, run `./media-server test-recovery` with a healthy stack and no active viewing/restoration. It temporarily substitutes an unavailable UUID, verifies all media ports close, restores the original profile in a `finally` block, and waits for all services, routing and aliases to recover. It includes Solver port 8191. This does not test a physical disconnect.

If the test process is killed before cleanup, compare `state/storage.json` with private `checks/storage-profile-before-recovery.json` and restore the verified original profile while in maintenance. Never create replacement mount directories to bypass the gate.

Completion requires fresh healthy endpoints, new process IDs after recovery and the matching receipt, not merely the presence of a process.

## Backups and logs

An hourly worker checks whether a daily backup is due. Snapshots live under `/Volumes/Media/media-server-backups/`; `backup` also creates a fresh timestamped snapshot. A manual snapshot counts toward that day's automatic backup. The seven most recently completed snapshots are retained by completion time. A file lock prevents overlapping backup writers; an interrupted partial snapshot is rebuilt from current settings on retry, so removed files cannot leak back into a completed backup.

Each SQLite database uses the online backup API and a quick integrity check. Other settings and the controller are copied privately; caches, cover artwork, media metadata, transcodes and logs are excluded. Consistency is per database, not one cross-application transaction. Keep an independent copy of important settings/media: the external snapshot is on the same disk as the library.

Snapshots also include the configuration-import, owner-deleted-torrent and one-time download-preference receipts under `checks/`. Restore these alongside `state/`; they prevent re-importing intentionally removed records or overwriting newer preferences.

The controller rotates its top-level logs at 10 MiB with three older copies. Copy/truncate preserves descriptors but can lose a small concurrent logging interval. App-owned nested logs have their own policies. Inspect `supervisor.log`, `supervisor.stderr.log` and the affected service's stdout/stderr when a check fails.

## LAN routing

`./media-server mdns --interface en1` selects the verified LAN interface; inspect the real interface if networking changes. `./media-server proxy` installs/verifies Caddy and enables port-free routing. Configuration-only changes apply within five seconds. `mdns --disable` or `proxy --disable` affects only that feature; direct app ports remain diagnostic fallbacks from the Studio; with password-free home management enabled, they are loopback-only.

Clients must share the LAN and permit multicast. A successful local bind does not prove Apple TV/iPad access; verify names and HTTP responses from another device. The controller adapts publications to interface address changes without changing router or client DNS settings.

## Password-free home management

Inputs: a healthy seven-service deployment, enabled Caddy and the independently verified private IPv4 LAN subnet. Start in the Studio runtime. The owner explicitly selected this policy on 15 October 2026. All devices on that subnet receive management access; Jellyfin keeps its personal account.

1. Check the actual interface address and subnet mask. The current home network is `192.168.50.0/24`.
2. Run `./media-server home-access --network 192.168.50.0/24`. The command validates and loads Caddy's peer-address restriction first, briefly stops only the five management apps, binds them to loopback, removes their local login prompts, and restarts them. Jellyfin and Solver continue running. Original Arr login rows and app API keys are retained.
3. Open all five `.local` management pages in a fresh browser without supplying credentials. Check their API/dashboard endpoints too; a login page with HTTP 200 is not success. Confirm the direct app ports are unreachable from another LAN computer.
4. Keep `state/home-access.json` with native-state backups. Rebuilding Caddy through `proxy` preserves this restriction. Its `remote_ip` matcher uses the actual connection peer, not a user-supplied forwarding header. Do not put a broad trusted proxy in front of this boundary without reviewing its effect.

Outputs are private `checks/home-access.json` and a `migration-backups/home-access-*` configuration rollback snapshot. Invalid/public/empty subnet policies fail. On failure, the command restores app login/bind settings before restoring the previous proxy policy; inspect status and the snapshot before retrying. If the command is killed mid-change, keep affected management apps stopped, restore its saved app settings, then its saved policy/Caddyfile and service definitions in that order. Do not delete only the network policy while leaving local login bypass enabled.

Completion requires password-free app content from the home LAN, explicit denial outside that subnet, closed direct management ports on the LAN, and unchanged Jellyfin account access. Disabling Caddy leaves these apps accessible only from the Studio itself. References: [Caddy peer-address matching](https://caddyserver.com/docs/caddyfile/matchers#remote-ip), [Sonarr local authentication policy](https://wiki.servarr.com/sonarr/settings#security).

## Subtitle policy

[English subtitles](subtitles.md) owns the current language profiles, provider coverage, automatic retry schedule, Jellyfin selection, verification and recovery.

## Import notifications

[Downloads appearing in Jellyfin](imports.md) owns Radarr/Sonarr import notifications, native movie identity sidecars and discovery troubleshooting.

## Additional proxy sites

Generated Caddy configuration imports `proxy-sites/*.caddy` under the runtime root, preserving separately maintained site definitions when media configuration is regenerated. Keep those definitions and their access policies under their own owners; the media LAN policy remains in the generated media blocks.

## Individual and group service controls

With the system supervisor running and storage verified, submit a scoped request from the installed controller:

```sh
~/.local/share/media-server/media-server control --service sonarr --action stop
~/.local/share/media-server/media-server control --service sonarr --action start
~/.local/share/media-server/media-server control --service media --action restart
```

Targets are `media` or one of `jellyfin`, `sonarr`, `radarr`, `jackett`, `bazarr`, `qbittorrent`, and `flaresolverr`; actions are `start`, `stop`, and `restart`. A media group start retains separately held individual services. Holds persist in private lifecycle state. Control waits for graceful exits and checks Arr activity before stopping; backups and lifecycle operations exclude each other. A pending result is not success: inspect `status`, resolve the ongoing operation, and repeat the same request to observe its result. It does not force-kill an operation merely because the client timed out. A verified storage failure remains an emergency gate and stops the owned stack.

The separate `stop` command still establishes whole-stack maintenance, and `start` resumes that maintenance workflow. Check status and service endpoints after any action; local tests do not establish live runtime health.

## Temporary media hold across a host restart

For a coordinated host restart, `control --service media --action stop --resume-on-boot` creates a temporary group hold after the graceful stop completes. Record the returned temporary hold ID. Restarting only the supervisor on the same boot does not clear it; a new macOS boot clears only the holds created by that operation, preserving earlier individual and group holds. This command controls media services and does not itself restart or power off the host.

If the host restart is cancelled, use `control --service media --action start --restore-temporary HOLD_ID`, replacing the placeholder with the returned ID. The exact ID prevents a stale rollback from releasing another hold. Inspect `status` and endpoint readiness after recovery. A pending or blocked result requires investigation; do not assume a timeout means the hold completed.
