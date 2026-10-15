# English subtitles

[Home](../README.md) · [Operation](operations.md)

Bazarr owns automatic English subtitle searches/downloads; Jellyfin owns the user's playback selection. Both acquisition policy and playback selection are explicit, including new imports and existing media.

## Configure or recover

Inputs: the healthy native apps, existing Bazarr/provider credentials, the media disk, and the intended Jellyfin user. Start at `http://bazarr.local` and `http://jellyfin.local` on the home LAN. Preserve native settings/online database backups before bulk edits. Application UI/API settings are the live owner; no credentials belong in this repository.

1. In Bazarr Settings → Languages, enable English and select/create the **English** profile. Request full English subtitles, forced off, no audio-language exclusion and no cutoff that could substitute Croatian. Current profile ID is 2. The prior Croatian/English profile remains selectable; existing sidecars are preserved.
2. Enable that profile as the default for both new movies and new series. Defaults do not change old entries: bulk-assign the profile to existing movies and shows too. Verify the profile on all current entries after assigning it.
3. Keep Sonarr/Radarr integrations and live event synchronization enabled, with deferred searches off and no monitored-only/tag exclusions. This includes restored unmonitored records with existing media without changing their Arr download monitoring. Native catalog synchronization is hourly; wanted-subtitle retries run every six hours for movies and episodes.
4. Keep the tested providers enabled: Titlovi, YIFY Subtitles and Gestdown. Gestdown adds English TV coverage; a real catalog lookup/search returned English matches during qualification. Provider credentials remain private. Use Wanted to inspect unresolved English requirements and System → Tasks to run missing-subtitle searches immediately. A green provider state does not prove a match exists for every release.
5. In Jellyfin's intended user's subtitle settings, select **English**, **Always Play**, and turn off remembering prior subtitle selections. Current API values are `SubtitleLanguagePreference=eng`, `SubtitleMode=Always`, `RememberSubtitleSelections=false`. Reload the client/reopen playback so it requests new defaults.
6. Check both subtitle availability and playback. Existing embedded English tracks satisfy Bazarr's English requirement; a Croatian track cannot. Jellyfin must identify the subtitle as English and select it by default. A retained movie selected English by default and the server returned its complete English WebVTT track successfully.

Outputs are native settings, assigned profiles and normal `.en.srt` sidecars when downloads succeed. Policy, provider and playback receipts plus before-change settings/database snapshots stay private on Studio.

Failure/resume: if a title remains Wanted, inspect its profile, actual file path, English track detection, provider throttle/health and matching score. Retry through Bazarr's task UI; do not relax match quality blindly or treat a Croatian subtitle as English. Restore configuration/database snapshots only with the affected app stopped. Provider availability and matching releases are external constraints; retries cannot guarantee a subtitle that has not been published. Speech-to-text generation is a separate, unconfigured fallback with its own compute requirements.

A new movie import received the default English profile and its English subtitle automatically. All three configured providers reported Good at qualification; unresolved matches remain visible in Wanted. New-episode event-to-file completion has not been tested with an actual new TV download. Missing payloads can leave episode records in the restored catalogs; those records do not establish file availability.

References: [Bazarr language profiles and defaults](https://wiki.bazarr.media/Additional-Configuration/Settings/Languages/), [provider settings](https://wiki.bazarr.media/Additional-Configuration/Settings/Providers/), [Jellyfin subtitle-mode behavior](https://github.com/jellyfin/jellyfin-web/blob/master/src/strings/en-us.json).
