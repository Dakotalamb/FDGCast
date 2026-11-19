# Recording Studio

Open **Recording Studio** in Companion. Connect OBS and refresh sources if prompted.

1. Choose **Same as my live picture**, or a preset for a different recording layout. Clean gameplay needs the original game source: a combined live picture cannot have its baked-in overlays removed.
2. Check the two labelled previews. For a different layout, choose existing OBS sources, move or resize them, or draw a crop on the live preview. Follow live scene is enabled by default. Switch it off to edit a particular scene. Save a default layout for scenes without their own setup.
3. Choose **Save recording setup**, then **Start this recording**. Wait for the status card to say **recording**. Stop and wait for **saved** before closing OBS or moving files.

The previews are local snapshots at up to one refresh every two seconds. They pause on hidden tabs and can be paused manually. They are layout guides, not a decoder view of recorded files.

## Folder and quality

Advanced options are under **Folder, quality, audio tracks & extra files**. A blank folder uses Windows Videos. Choose a writable local folder; network paths are not supported. MKV filenames are unique. Use OBS File → Remux Recordings for MP4 conversion. Existing recordings are not overwritten or deleted when a setup is removed.

Same-picture recording shares a compatible active main stream video encoder and inherits its actual dimensions/quality. Without a compatible active encoder, it encodes the current OBS output separately with the saved default recording bitrate. Custom layouts use their own H.264 encoding and can have different dimensions, bitrate and reduced frame rate. Automatic selection prefers available hardware; if an encoder cannot start, the status shows an error rather than silently switching a failed hardware recording to CPU encoding.

One file is the default. Up to three Recording Studio files can run simultaneously. Matching video settings/layouts and matching audio mixer tracks can share encoders. Different pictures still require rendering and encoding; hardware session limits, disk speed and available GPU/CPU capacity apply. Reusing a capture avoids opening another camera/game capture but does not make a different recording free of processing cost. Reduce recording size/frame rate or extra files if streaming performance suffers.

## Audio

Select OBS audio tracks 1–6. Track 1 is normally the full mix. For independent game/microphone/voice-chat tracks, first configure source routing in OBS Advanced Audio Properties. FDGCast records those mixer buses as separate AAC streams and does not alter routing. Selecting an empty mixer track records silence. The first selected track becomes the first audio stream in the file.

## Starts, stops and failures

Recording Studio does not replace OBS's standard recording controls. Manual recordings can continue when streaming stops. The optional **Automatically start and stop this recording with my stream** setting applies to future main-stream starts after OBS receives the saved setup; it does not start recording an already running stream. Only files started automatically by that option stop automatically with that stream.

Stop Recording Studio files before changing saved settings or their folder. Changing scene collections or OBS profiles and closing OBS stop/drain Recording Studio outputs. Companion disconnecting does not stop files: use **FDGCast Control → Stop Recording Studio files** inside OBS. Reopen Companion to see current status. A disconnected card shows the last known file information with **state unknown**.

Errors such as missing sources, wrong scene collection, unavailable encoders, unwritable folders and low disk space are shown locally. Starts require at least 256 MB available when Windows can report it; active files stop below 128 MB. These thresholds are emergency guards, not an estimate of the space needed for a stream. Removing a source while recording can leave its picture blank; keep recorded sources available until stopping.

Local recording paths and raw file errors are excluded from exported diagnostic reports and Hub delivery. No public-platform broadcast is needed for Recording Studio.

## Reference and validation

The uploaded Source Record project was inspected to understand OBS recording patterns. Its source was not copied or bundled. FDGCast uses its existing layout geometry plus an independent renderer/output manager and the standard libobs view, encoder and file-output APIs.

Automated release checks cover configuration/security boundaries, browser interactions and real OBS recordings decoded with FFmpeg: different pictures, shared active stream encoding, two distinct mixer tracks, stop/restart, linked/manual lifecycle isolation, unique paths and shutdown. Physical capture devices, hardware encoders and game-specific performance still depend on the user's Windows PC.
