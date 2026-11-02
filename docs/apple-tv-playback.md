# Apple TV playback

On 1 November 2026, the working configuration for the tested Apple TV HD and normal Swiftfin 1.6.1 app was:

- Video Player Type: **Swiftfin**
- Compatibility: **Compatible**
- Bitrate: **4 Mbps**

The viewer confirmed smooth playback. The observed stream advanced with hardware-accelerated H.264 conversion at 720p and AAC audio. This setting trades picture detail for a lower bitrate; it does not guarantee smooth playback for every source or network.

An earlier Native player and 6 Mbps recommendation was superseded: Native produced a black screen during the later test. The working settings were selected in Swiftfin itself. Another ordinary launch and a different title have not been checked, so persistence remains unverified. A separate audio/video synchronization issue was also observed across apps and remains unresolved.

## Verify playback

1. In normal Swiftfin's Settings, select the working player, compatibility and bitrate above. Other app versions or devices may present different options.
2. Start playback and check picture, motion and sound. If symptoms recur, distinguish buffering from uneven motion and record the source and timing before changing settings.
3. On the server, inspect the current Jellyfin session and its current transcoding log. Confirm that playback advances and, when conversion is active, verify the actual codec and hardware acceleration. A saved preference or old log alone does not establish the current stream.
4. After a clean ordinary app launch and on another title, repeat the observation before claiming the settings persist. If settings cause trouble, restore the previous choices in the app.

This observation concerns a specific installation, app version and playback session; it is not a universal Apple TV compatibility claim.
