# Build with: .venv/bin/python scripts/build_app.py
from pathlib import Path

root = Path(SPECPATH)
a = Analysis(
    [str(root / "app_entry.py")], pathex=[str(root)],
    binaries=[], datas=[], hiddenimports=["hid"], hookspath=[], hooksconfig={},
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
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": "Zeigt Titel aus Spotify und Music auf deiner G15 an und steuert die Wiedergabe über die Displaytasten.",
        "NSInputMonitoringUsageDescription": "Liest die G- und Displaytasten deiner Logitech G15.",
    },
)
