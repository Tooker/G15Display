# Changelog

## 1.1.0 – Unreleased

- Add English, Spanish, French, and German modes for the native app, macro
  window, status/errors, and LCD dashboard.
- Switch languages immediately from the main window; save the selection across
  restarts. First launch follows supported macOS language preferences with an
  English fallback.
- Preserve running timers, recording state, macro names, and assignments when
  changing language.
- Add `--language en|es|fr|de` to command-line tools and localized macOS
  permission descriptions. The documentation remains in English.
- Add nine localization tests, bringing the automated suite to 63 tests.

## 1.0.0 – 2026-10-19

First public release for the first-generation Logitech G15 (folding display,
blue backlight) on macOS with Apple Silicon.

- Standalone Mac app with a menu bar item, live preview, and automatic reconnection.
- Display pages for the clock, Codex limits, local Codex tasks, timer,
  Pomodoro, Spotify/Apple Music, and network activity.
- Display-button controls and detection of G1–G18 and M1–M3.
- Keyboard macro recording with timing and separate M-banks;
  stop recording or playback using the app or MR.
- Python source code, build instructions, and 54 automated tests.

### Download

Extract `G15-Display-1.0.0-macOS-arm64.zip` and open `G15 Display.app`.
No separate Python installation is required. `SHA256SUMS.txt` contains the
archive's checksum.

### Requirements and known limitations

- macOS on Apple Silicon; no Windows or Intel Mac build is included.
- Ad-hoc signed, without Apple notarization. macOS may initially block
  downloaded copies.
- The app and LCD interface currently use German labels; the documentation is
  in English.
- Macro recording requires Input Monitoring; playback requires Accessibility.
  Keyboard events are captured only during an explicitly started recording,
  then system-wide for up to 60 seconds / 500 events.
- Codex pages require an existing local Codex login; task status is derived
  from local logs and may be delayed.
- Music may require macOS permissions for Spotify or Music.
- M-key LEDs are not synchronized yet. Brightness control and launch at login
  are not implemented.
- The display and many special keys were checked on physical hardware.
  Macro recording/playback has automated coverage using simulated events;
  a complete live test with user-granted permissions remains outstanding.
