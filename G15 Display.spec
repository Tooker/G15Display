# Build with: .venv/bin/python scripts/build_app.py
from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / "app_entry.py")], pathex=[str(root)],
    binaries=[], datas=[(str(path), path.name) for path in sorted((root / "assets" / "localizations").glob("*.lproj"))], hiddenimports=["hid"], hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=["tkinter", "numpy", "matplotlib", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="G15 Display",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, argv_emulation=False, target_arch="arm64",
    codesign_identity=None, entitlements_file=str(root / "app.entitlements"),
)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="G15 Display")
app = BUNDLE(
    collection, name="G15 Display.app", icon=str(root / "assets" / "G15.icns"),
    bundle_identifier="local.g15display.app",
    info_plist={
        "CFBundleDisplayName": "G15 Display",
        "CFBundleShortVersionString": "1.1.0",
        "CFBundleVersion": "110",
        "CFBundleDevelopmentRegion": "en",
        "CFBundleLocalizations": ["en", "es", "fr", "de"],
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": "Shows Spotify and Music tracks on your G15 and controls playback using the display buttons.",
        "NSInputMonitoringUsageDescription": "Captures keyboard sequences only during a macro recording you start and reads G15 special keys. Reads normal G15 key states only during a key test you start.",
    },
)
