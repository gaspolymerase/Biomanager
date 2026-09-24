# PyInstaller spec for BioManager desktop build.
#
# Build:   pyinstaller Biomanager.spec --clean --noconfirm
# Output:  dist/BioManager.app  (macOS)  /  dist/BioManager/  (Win/Linux)
#
# The spec bundles app/static + app/templates as read-only resources. SQLite
# DB and user uploads land in ~/Library/Application Support/Biomanager/ at
# runtime (see app/paths.py).

# noinspection PyUnresolvedReferences
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

datas = [
    ("app/static", "app/static"),
    ("app/templates", "app/templates"),
]

# pywebview backends + Flask use a few modules PyInstaller's static analysis
# can miss.
hiddenimports = (
    collect_submodules("webview")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + ["psycopg"]
)


a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BioManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="BioManager",
)
app = BUNDLE(
    coll,
    name="BioManager.app",
    icon=None,
    bundle_identifier="org.biomanager.desktop",
    info_plist={
        "NSHighResolutionCapable": "True",
        "LSBackgroundOnly": "False",
        "CFBundleShortVersionString": "0.1.0",
    },
)
