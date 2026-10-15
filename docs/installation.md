# Installation and rebuild prerequisites

[Home](../README.md) · [Operation](operations.md) · [Migration](migration.md)

## Scope

The existing Studio has already completed installation and migration. The controller records that deployment's paths, package versions and private state layout. This document describes its prerequisites and deliberate rebuild sequence; it does not claim a tested blank-machine one-command installation.

Restore current native backups to rebuild the configured services. `packages` downloads the qualified archives; `stage` selects their native applications and regenerates service definitions. Staging requires headless qBittorrent and must be done in maintenance with a verified settings backup. Staging requires complete native settings and all six core applications; it fails without replacing service definitions when a restore is incomplete. It does not replace restored databases or recreate private application accounts. Source-host copying and sample-library commands are absent from the controller.

## Dependencies and versions

The verified host is Apple Silicon with Homebrew under `/opt/homebrew`. The controller requires Python 3.11+ and selects `/opt/homebrew/bin/python3.14`. Bazarr's environment was built with mise Python 3.13.16. Rebuilding native components also needs Apple's command-line tools and the dependencies installed explicitly by `headless`.

| Component | Qualified version / implementation |
| --- | --- |
| Jellyfin | 12.2.0 native ARM64 bundle, bundled FFmpeg/FFprobe, VideoToolbox |
| Sonarr | 4.0.20.3014 native bundle |
| Radarr | 6.4.4.10685 native bundle |
| Bazarr | 1.6.2, private Python environment, native ARM UnRAR 7.23 |
| Jackett | 0.24.2850 native ARM64 |
| qBittorrent-nox | 5.2.3, upstream commit `0b63c3d17373f6132ea211c9dcd4241284ccdfaf` |
| Private libtorrent | 2.0.15, commit `1eb18faeae156d8dbbab42935c082f8b81f50989` |
| FlareSolverr | 3.5.2, commit `93125d6ea6956906c8dfa29e169b2dc67d993dc3` |
| Solver browser/driver | Managed Chrome 155.0.8059.40; ARM64 ChromeDriver 155.0.8059.79 |
| Caddy | 2.11.7 native ARM64 |

Some application-download helpers use upstream `latest` routes with expected hashes/sizes. Requalify changed artifacts; a future upstream release is not implicitly verified. Keep private installers/build receipts outside Git.

## Rebuild sequence

Inputs: a verified private native-state snapshot, compatible application bundles/dependencies, the registered media disk and its storage profile, and this repository. Start in the Studio owner's Terminal. Preserve any newer state before restoring; do not merge live databases or run applications while replacing them.

1. Restore the private runtime outside iCloud at `~/.local/share/media-server/`, including the snapshot's `state/` and `checks/` receipts. Keep private settings and credentials owner-only. A settings snapshot does not contain application bundles or the media library; recover/reinstall those separately. Existing native-state paths and the media symlink must match the intended owner/volume.
2. Copy the reviewed controller there as `media-server` and make it executable. Confirm the Python paths, app locations and `state/services.json` before starting anything. `packages` and `stage` can recover native bundles from verified installers; they are not a substitute for the restored configuration.
3. With fresh confirmed maintenance (or the system job unloaded), `./media-server headless` builds/selects the pinned no-GUI qBittorrent while preserving its profile. It builds private compatible libtorrent, bundles required Qt libraries and signs/verifies the result. If a build sees incompatible global libtorrent headers, inspect the conflicting Homebrew linkage; do not remove unrelated dependencies blindly.
4. Run `./media-server solver` with the owned stack stopped. `headless`, `solver` and `stage` enforce that requirement before changing applications. It clones pinned upstream source, installs a private environment, prepares the managed browser/driver, applies the macOS headless adjustment, patches/signs the driver and sets Jackett's loopback Solver URL. Initial browser staging requires the qualified installed Chrome version; qualify a matching browser/driver pair before changing versions.
5. Validate the restored storage profile and stable media link with `./media-server check`. This must succeed before boot activation. Disk registration is a separate [migration step](migration.md), not a formatter or restore tool.
6. Install the system boot service using the handoff below, then resume and verify through the [operating procedure](operations.md).

If an application/dependency is missing, keep maintenance enabled and repair only that component. `start` requires the installed system boot service; it cannot create a login job. If boot activation fails, the maintenance hold remains in place.

## System boot service

Inputs: native services configured, headless qBittorrent selected, storage checked, and any old media login supervisor stopped/unloaded. Start in the private runtime as the ordinary owner.

```sh
./media-server prepare-boot
sudo /bin/sh "$HOME/.local/share/media-server/install-boot.sh"
./media-server status
./media-server start
```

`prepare-boot` creates a maintenance marker and a bounded administrator installer. That installer places a root-owned plist in `/Library/LaunchDaemons`, removes any unloaded media login plist and bootstraps the system job. Its `UserName` remains the ordinary runtime owner; it does not run user-controlled Python as root.

Confirm `job_domain=system`, then fresh healthy status after `start`. Startup refuses a plist for another runtime/owner or a loaded job still using another script; reinstall/reload the matching boot job and keep maintenance enabled on failure. macOS administrator authentication and removable-volume privacy permission are native OS handoffs. If Python blocks opening the external storage marker, inspect the Studio screen for the relevant permission prompt and resolve it before treating startup as successful. Do not change unrelated automatic-login settings.

Completion requires the system-domain job, normal-user execution, verified storage and authenticated application checks. A configured LaunchDaemon is not itself evidence of a fresh cold boot or logged-out playback.

## Configuration ownership

`state/services.json` defines owned processes and environments. `storage.json` defines the selected volume and marker; `mdns.json` and `proxy.json` select LAN routing. `home-access.json` owns the password-free management subnet; preserve it alongside the loopback/login settings. `state/access.json`, app config files and Jellyfin session state contain secrets and stay private. Do not publish generated plists, service-state dumps, logs, database copies or recovery archives.

Upstream references: [qBittorrent](https://github.com/qbittorrent/qBittorrent), [libtorrent](https://github.com/arvidn/libtorrent), [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr), [Caddy](https://caddyserver.com/docs/).
