# G15 Display

A Python controller for the monochrome display of the **first-generation
Logitech G15** (folding display, blue backlight), running on macOS.
Requires Python 3.10 or later when running from source.

## macOS app

Download version **1.0.0** from [GitHub Releases](https://github.com/Tooker/G15Display/releases/tag/1.0.0).
`G15-Display-1.0.0-macOS-arm64.zip` contains the standalone Apple Silicon app.
Extract it and copy `G15 Display.app` to your Applications folder.

When built locally, the app is at **`dist/G15 Display.app`**. Double-click to
open it; no Terminal or separate Python installation is required. The Apple
Silicon app is approximately 34 MB uncompressed.

The source version (1.1.0, not yet released) supports **English, Español,
Français, and Deutsch** for both the app and LCD. Select a language at the top
right of the main window. The choice is saved and applied immediately, including
to an open macro window, without resetting timers or changing macro assignments.
On first launch, the app uses the first supported macOS preferred language,
falling back to English. System permission prompts follow macOS language settings.
The published 1.0.0 download still has the original German interface.

Documentation remains in English. The German button names below refer to the
German mode and the 1.0.0 download; their English meanings are included.

- Live preview using the same pixel font as the keyboard display.
- Switch pages using the page selector, on-screen buttons, or physical G15 buttons.
- `Verbinden` / `Trennen` (Connect / Disconnect) controls device access.
  Preview and timers continue while disconnected; quitting discards timer state.
- Timer and Pomodoro durations are configurable and saved in macOS preferences.
  `Zeiten anwenden` (Apply durations) resets both timers.
- Closing the window keeps the app running under **G15 in the menu bar**.
  Use that menu to reopen the window or quit.
- The app automatically reconnects after unplugging and reconnecting the G15.
- Only one program per user can control the display. If the older Terminal
  dashboard is still running, stop it with Ctrl+C. The app waits and then connects.

macOS may request permission for **G15 Display** to access music players.
If keyboard access is unavailable, `Zugriff …` (Access) opens Input Monitoring
in System Settings. Permissions are never granted automatically.
Codex limits require an existing signed-in ChatGPT/Codex installation;
the app does not bundle its credentials or executables.

The app is ad-hoc signed, without a Developer ID or Apple notarization.
macOS may initially block a downloaded copy. The entire `.app` can be moved;
it does not depend on the project's `.venv` directory.

### Rebuilding the app

Create the Python environment described under [Running from source](#running-from-source), then run:

```sh
.venv/bin/python -m pip install -e '.[app]'
.venv/bin/python scripts/build_app.py
```

`G15 Display.spec` bundles Python, Cocoa/PyObjC, Quartz, HIDAPI, Pillow, and
psutil. The UI runs on the macOS main thread; data polling, USB access, and
reconnection run separately. Updated command-line tools share the same device
lock. App errors are logged to `~/Library/Logs/G15 Display.log`.

### G-keys and macro recording

Open **G-Tasten …** (G-keys) in the main window or **G-Tasten / Makros …**
(G-keys / Macros) from the menu bar:

1. Select a bank **M1–M3** and target **G1–G18**, optionally entering a name.
2. Click **Aufnehmen** (Record). Recording starts after three seconds;
   switch to the target application during the countdown.
3. Type the desired sequence, including any keyboard shortcuts.
4. Click **Stoppen** (Stop) or press the physical **MR** key. The recording
   is assigned to the selected G-key and saved locally.
5. Press that G-key to play the macro in the currently active application.
   **Testen** (Test) also gives you three seconds to focus the target application.

During recording, a red status message appears in the macro window and
**● REC** appears in the menu bar. Only keyboard events are captured, not mouse
movements. No global keyboard listener is installed outside an explicitly
started recording. Recordings are limited to 60 seconds or 500 events.
Closing the macro window cancels recording. Canceled, empty, or system-interrupted
recordings do not replace the previous macro. G-key macros cannot play while
recording.

Recording requires macOS **Input Monitoring** permission; playback requires
**Accessibility** permission. The two permission buttons open the corresponding
System Settings pages. Restarting the app may be necessary after granting access.
The app does not grant itself permission.

**MR also stops active or scheduled playback.** Canceling playback releases any
keys still held by the macro. A second playback cannot start while one is running.
Synthetic playback events are tagged and excluded from recording.

Press a physical M1/M2/M3 key or use the bank selector to activate that bank.
The M-key LEDs are not synchronized yet. Existing G-key mappings in other
programs are not removed and may respond at the same time.

Macros are stored in
`~/Library/Application Support/G15 Display/macros.json`, using local file
permissions and atomic writes. A corrupt file is not overwritten. The file
contains keycodes, modifier flags, and timing, and is not included in Git.
Recordings carry a platform identifier; a macOS macro will not play on Windows
using incompatible keycodes.

## Testing normal typing keys

Open **Key test …** from the main window or the menu bar. This separate test
reads the physical G15 v1 typing interface (`046d:c221`, interface 0), including
letters, numbers, function keys, modifiers, and Backspace. It is independent of
the G-key reader and excludes virtual keyboards and other connected keyboards.
The default test key is **Backspace ⌫**.

1. Release all keys and select the key to test.
2. Click **Start**, then slowly press and fully release that key exactly ten times.
3. Click **I pressed ten times – evaluate**. The test stops and compares your
   reference count with the USB press/release count.

The display shows presses, releases, current/last received state, hold duration,
and rapid represses within 50 ms. Holding a key or receiving an identical report
does not count as another press. Raw USB states do not include macOS-generated
key repeat. A long hold is highlighted after two seconds, but only you can confirm
whether the physical key has already been released.

Rapid represses are timing clues, not proof of switch bounce. A count mismatch
is meaningful only if you really pressed exactly ten times; it does not identify
whether the cause is the key, keyboard electronics, or connection. A missed
physical press cannot be inferred from silence alone. Ten successful presses do
not rule out intermittent dropouts. Invalid reports, rollover, and connection
errors make the measurement incomplete rather than reporting a faulty key.

Access is shared and read-only; no LED settings or keyboard configuration are
written. The actual HID report descriptor must match the verified G15 format
before measurement starts. Input Monitoring permission may be needed. Only
aggregate state/counts for the selected key are retained in memory; no typed text
or ordered key log is saved. Stop, closing the test window, quitting, or the
two-minute limit ends measurement. Stopped values describe the last received
state, not a live keyboard state. Changing the test key or starting again resets
the counters. USB key names describe positions; Y/Z differ between US and German
layouts, as noted in the selector.

## Windows compatibility

**The current app is for macOS and does not run unchanged on Windows.**
The Python HIDAPI wrapper supports Windows, Linux, and macOS:
[project documentation](https://github.com/trezor/cython-hidapi).
The image format, pixel font, timers, and G15 key decoder are largely independent
of the operating system. A Windows port still requires:

| Component | Current implementation | Required for Windows |
| --- | --- | --- |
| UI | Cocoa/PyObjC | A Windows-compatible UI |
| Macro recording/playback | Quartz | Native Windows keyboard integration |
| Device lock | `fcntl` | A Windows-compatible lock |
| Network interface selection | `/sbin/route` | Windows route lookup |
| Music information | AppleScript | Windows player/media integration |
| App package | arm64 `.app` | A separate build on Windows |

USB reports and G-keys also need physical testing on Windows, particularly
alongside Logitech software. No Windows hardware test has been performed.
PyInstaller builds Windows executables on Windows; it is not a cross-compiler:
[PyInstaller documentation](https://pyinstaller.org/en/stable/).

## Repository

Public repository: [Tooker/G15Display](https://github.com/Tooker/G15Display),
default branch `main`. Source code, tests, documentation, and build instructions
are versioned. Python environments, app builds, previews, local configuration,
and logs are excluded. Standalone app packages are published as release assets.

## Running from source

Create and install a local Python environment in the project directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Then run:

```sh
# List connected display interfaces
.venv/bin/python -m g15display devices

# One line per argument, up to four lines
.venv/bin/python -m g15display text "Hello G15!" "Python on the G15" "160 x 43 pixels"

# Live clock; stop with Ctrl+C
.venv/bin/python -m g15display clock

# Run for a limited time
.venv/bin/python -m g15display clock --seconds 5

# Clear the display
.venv/bin/python -m g15display clear

# Show special-key events in Terminal and on the LCD
.venv/bin/python -m g15display keys --display

# Stop the key test after 30 seconds
.venv/bin/python -m g15display keys --display --seconds 30

# Generate a PNG preview without USB access
.venv/bin/python -m g15display clock --preview preview.png
```

After installation, `.venv/bin/g15` accepts the same arguments.
The last transmitted image remains on the display after exit; use `clear` to
remove it. The clock uses the computer's local time zone.

## Dashboard menu

On macOS, **double-click `G15-Menue.command`** to launch the dashboard in a
separate Terminal window. Press **Ctrl+C** there to stop it. This also allows
macOS to show permission prompts for music player access.
Alternatively, run it from the project directory:

```sh
.venv/bin/python -m g15display menu

# Run in a specific language (en, es, fr, de)
.venv/bin/python -m g15display menu --language fr

# Start on a specific page
.venv/bin/python -m g15display menu --page limits

# Custom durations in minutes; four Pomodoro work rounds
.venv/bin/python -m g15display menu --timer-minutes 10 --work-minutes 25 --break-minutes 5 --rounds 4

# Preview a page as a PNG without USB (queries real data sources)
.venv/bin/python -m g15display menu --page network --preview preview.png

# Combine all seven pages and the menu into one preview image
.venv/bin/python scripts/preview_menu.py
```

The **four function buttons below the display, from left to right**:

| Key | On a page | In the menu |
| --- | --- | --- |
| L2 | Previous page | Select previous entry |
| L3 | Next page | Select next entry |
| L4 | Perform the displayed action on release | Open selected page |
| L5 | Open the menu | Return to the clock |

Button labels always appear at the bottom of the LCD. L1 also opens the menu.
The dashboard has seven pages:

| Page | Data and controls |
| --- | --- |
| Clock | Local time, date, weekday, and calendar week |
| Codex limits | Remaining percentages as bars; L4 switches to reset times |
| Codex activity | Locally detected active task count and chat name; L4 shows the next task |
| Timer | Five minutes by default; L4 starts/pauses, hold L4 for at least one second to reset |
| Pomodoro | 25 minutes of work, five-minute breaks, four work rounds; same controls as the timer |
| Music | Spotify and Apple Music: title, artist, progress; L4 toggles play/pause |
| Network | Default interface, IPv4 address, and current download/upload rates in KiB/s or MiB/s |

Timers continue when switching pages and use a monotonic clock. Phase changes
show a five-second message in the header. A Pomodoro session ends after its
last work round. An action after completion restarts the timer. Timers are not
persistent and currently make no sound; quitting discards their state.

**Codex limits:** Uses `codex app-server --stdio` with the existing local Codex
login. The executable is located through PATH or known ChatGPT/Codex app
installation paths. Only initialization and `account/rateLimits/read` are called;
there are no model requests, chat changes, or quota resets. `ZEIT` (Time) only
shows reset times. The actual returned usage windows are used; a missing window
is not displayed as 0%. Updates every 60 seconds. Reference:
[official OpenAI documentation](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt).

**Task status:** A separate Codex server does not know which tasks are running
in the desktop app. This page therefore reads local metadata from
`~/.codex/state_*.sqlite` and `task_started`, `task_complete`, and `turn_aborted`
events from the associated session logs. It considers the 32 most recently
updated, non-archived chats from the past 24 hours. The database is opened
read-only and log files are not modified. After ten minutes without new log data,
a task that appeared active is treated as uncertain. Remote tasks are not
included. This is a local approximation that depends on the installed Codex
log format; the display explicitly labels it as local logs. Updates every
three seconds.

**Music:** Only already-running Spotify/Music processes are queried; no player
is launched. When both are running, a playing player takes priority, with Spotify
winning ties. Polling runs every three seconds. macOS may request Automation
permission for Spotify/Music, granted to the app, Terminal, or Codex process
launching the query. Denied access and timeouts produce an appropriate LCD error
(access, timeout, or query failure). Queries wait up to ten seconds to allow time
for the initial permission prompt. The other player is still checked; a failed
player is retried after 30 seconds. `PLAY` without a selected player does not
launch an application. Other multimedia keys are not handled by this reader.

**Network:** Measures byte counters on the default interface, which may be a
tunnel when using a VPN. This is observed traffic, not an internet speed test.
The first rate calculation requires a second sample. Updates approximately
once per second.

Slow data queries run in the background. Navigation and timers remain responsive
when Codex or a player does not answer. Missing data is shown as unavailable
instead of being replaced with sample values. The dashboard uses `psutil` for
network and player detection; it is installed with the project.

The command-line tools also accept `--language en|es|fr|de`, either before or
after the subcommand. Without it, they use the locale from the shell environment
and fall back to English. Library objects retain German as their default for
compatibility; pass `language="en"`, `"es"`, `"fr"`, or `"de"` explicitly.

The LCD font uses fixed 5×7 pixel characters with a one-column gap. Large digits
are scaled to exactly twice their size. All text is uppercase; German umlauts
are rendered as AE/OE/UE and ß as SS. French and Spanish accents are reduced to their base letters on the LCD;
the native app retains accented characters. Each line fits at most 26 characters.
Scrolling text waits three seconds, then advances one character per second.
After font or layout changes, stop the running Terminal dashboard with Ctrl+C
and restart it to load the changes.

## Custom content

Pillow draws a 160 × 43 pixel monochrome image. White represents an active/dark
LCD pixel; black represents the background. Text that exceeds the line width is
clipped on the right. The preview shows active pixels dark against a blue background.

```python
from PIL import Image, ImageDraw
from g15display import G15

image = Image.new("1", (160, 43))
draw = ImageDraw.Draw(image)
draw.rectangle((0, 0, 159, 42), outline=1)
draw.text((8, 12), "My first display", fill=1)

with G15() as lcd:
    lcd.show(image)
```

`render.py` generates content; `display.py` handles USB transport. This separation
allows the transport layer to be replaced independently with Rust later.

## Reading keys

`keys` reads **G1–G18**, **M1–M3**, **MR**, **L1–L5**, and the **LIGHT**
backlight key. L1 is the display switch button; L2–L5 are its four function
buttons. The mapping follows the G15 v1 protocol in libg15; individual keys
should be checked on your own device. Normal letter, number, and media keys
belong to the other keyboard device and are not read in this mode.

The G15 sends a nine-byte input report with ID **2**. Its bits describe the
currently held special keys. `keys.py` decodes these states into **press** and
**release** events. Simultaneous keys are supported. Identical reports do not
produce duplicate events; timeouts and other report IDs do not release keys.
There is no automatic key repeat. A key already held at startup is reported as
pressed when the first valid report arrives. Unplugging the keyboard ends the
command with an error.

Example: switch to the clock with a display button:

```python
from g15display import G15, clock_screen

with G15() as lcd:
    while True:  # Stop with Ctrl+C
        for event in lcd.read_keys(timeout_ms=100):
            if event.name == "L2" and event.pressed:
                lcd.show(clock_screen())
```

This draws the clock once when L2 is pressed. A live clock also needs periodic
redrawing. `read_keys()` waits up to the specified positive number of milliseconds
per report. `lcd.held_keys` returns the last received state.

With `--display`, the key test replaces the current LCD content. Without it,
events are printed only in Terminal. This command does not assign key mappings;
existing mappings in other programs may still respond in parallel.

## USB and macOS

The controller uses `hidapi` (Python import `hid`) and Pillow. The display controller addresses only
**046d:c222**, the G15 v1 display/special-key device. The separate, explicitly
started typing-key diagnostic opens **046d:c221**, interface 0, read-only in
shared mode.

On macOS, shared access is enabled through HIDAPI's public
`hid_darwin_set_open_exclusive(0)` function. The Python wrapper does not expose
this function, so `ctypes` loads it from the wrapper's own bundled library.
No second HIDAPI installation is needed. This setting prevents macOS or other
keyboard tools from being excluded from the device. If multiple HID collections
exist, the vendor-specific collection is preferred. Multiple connected G15
keyboards are not selected automatically.

The LCD receives output report **3**, containing **992 bytes**, including a
32-byte header. Six bands of 160 bytes follow. Each byte describes eight vertical
pixels, least significant bit at the top. Only three bits are visible in the
last band. Protocol references:
[libg15.h](https://github.com/vividnightmare/libg15/blob/master/libg15.h) and
[libg15.c](https://github.com/vividnightmare/libg15/blob/master/libg15.c).
The Python implementation was written from scratch.

For access errors, close other display programs. If macOS requests permission,
check the launching Terminal or Codex under **System Settings → Privacy & Security
→ Input Monitoring**, then restart it. The controller installs no system driver
and does not require sudo.

Unplugging the keyboard ends a running command-line transfer with an error.
Restart the command after reconnecting. The native app reconnects automatically.
Macro assignments are available in the macOS app. Brightness control and launch
at login are not implemented yet. A successful write confirms USB transmission;
the result must also be checked on the physical LCD.

## Validation and tests

Hardware checks on **2026-10-19**, using a connected G15 v1 on macOS with Apple
Silicon: device detection, a complete 992-byte text image transfer, and a
three-second clock run succeeded. Environment: Python 3.14.6, hidapi 0.15.0,
Pillow 13.0.0. The PNG preview was visually checked and the user confirmed the
text on the physical LCD. A subsequent live key test received press and release
events for L2–L5, G1–G5, G7–G10, and G12–G18. Other keys follow the protocol
mapping but have not each been confirmed on hardware.

All 75 automated tests pass, covering menu navigation, timers/Pomodoro,
background operation while switching pages, data sources, and error handling.
Limits, local task metadata, and network data were retrieved live. After macOS
permission was granted, Spotify returned the paused title, position, and duration;
Apple Music returned `stopped`. Apple Music title display and play/pause control
have not been confirmed live; testing did not change playback.

The bundled app was opened and its preview, real data sources, and G15 connection
were verified. The package check confirms arm64, a bundled Python runtime,
HIDAPI 0.15.0, and 992-byte reports. The ad-hoc code signature was verified.
Macro tests additionally cover profile persistence, separate M-banks, start/stop,
cancellation with key release, platform identifiers, and recording permissions
using simulated keyboard events. Localization tests cover all four languages,
format placeholders, compact LCD labels, language switching during a timer and
a recording, preservation of user content, and command-line language selection.
The native macro window and normal app exit
were checked. All four native language modes were checked visually, including
the French macro window, and the selected language persisted across an app restart. A complete live recording/playback test with user-granted macOS
permissions remains outstanding.

`scripts/preview_menu.py` generates the combined page preview at
`previews/dashboard.png`. During development, the Codex sandbox blocked USB
access, so hardware tests ran with approved device access. For your own command-line tests,
run the commands in Terminal. The typing-key diagnostic also verifies the
physical keyboard descriptor and covers report decoding, count comparisons,
duplicate reports, hold durations, rollover gaps, connection failures, and cleanup
in automated tests. A ten-press Backspace test on hardware still requires the
user to supply the physical presses.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests also cover pixel positions, band boundaries, headers, unused bits, device
selection, incomplete transfers, key decoding, simultaneous keys, press/release
edges, ignored reports, and cleanup after USB errors.
