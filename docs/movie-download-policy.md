# Compact HD movie policy

The optional `studio/movie-download-policy.py` configures selected Radarr quality profiles for 720p and 1080p, prefers YTS/YIFY and 1080p, and sets size limits. The quality definitions and indexer maximum size are global Radarr settings, so applying this affects other profiles too. Review the values and your existing Radarr settings before applying; this policy is a preference, not a guarantee of a particular file size or release.

## Review and apply

Start on the configured host with a running local Radarr at `127.0.0.1:7878`, Python 3, the private Radarr configuration at `~/.local/share/media-server/state/radarr/config.xml`, and a backup. Find the intended profile IDs in your own Radarr installation. They are installation-specific. Run the script without `--apply` first, specifying each profile deliberately:

```sh
python3 studio/movie-download-policy.py --profile-id PROFILE_ID
```

Replace the placeholder with your own numeric profile ID; repeat `--profile-id` for each selected profile. The dry run reads and displays current settings; protect its output. After reviewing the settings and impact, repeat the command with `--apply`. The script writes private before/after snapshots under `~/.local/share/media-server/checks/movie-download-policy/`, then reads settings back. A failed or interrupted run may have applied only part of the policy: inspect Radarr and the before snapshot before retrying.

For rollback, use the private `before.json` snapshot to restore the original selected quality profiles, quality definitions and indexer configuration through Radarr's API or UI. Restore or remove the policy's custom formats only after checking whether anything else now uses them. Verify the restored settings and profile assignments in Radarr. Keep snapshots private; they can contain installation-specific configuration. No script action changes already downloaded media.
