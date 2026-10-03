"""What the window needs on Windows, so BioManager runs on Windows 10 as on 11.

The window is Microsoft Edge WebView2 (pywebview's edgechromium backend),
hosted through .NET Framework. Windows 11 has both. A Windows 10 PC may lack
WebView2 (or, before the 2016 Anniversary Update, a new enough .NET), and
then pywebview quietly falls back to Internet Explorer's engine, which can't
run the app: a blank or broken window. So desktop.py asks `missing()` before
opening the window, and without what it needs opens the app in the web
browser instead (`run_in_browser`), offering Microsoft's WebView2 installer.

Files unpacked from a downloaded zip carry Windows' "came from the internet"
mark, and .NET refuses to load an assembly that has it (HRESULT 0x80131515),
which stops the window as well. `unblock()` removes the mark from the app's
own DLLs, as right-click → Properties → Unblock would.
"""
from __future__ import annotations

import os
import platform
import webbrowser
from pathlib import Path

# Microsoft's "Evergreen Bootstrapper": a small installer that fetches the
# current WebView2 Runtime.
WEBVIEW2_DOWNLOAD = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
# pywebview's own thresholds (webview/platforms/winforms.py, _is_chromium):
# below them it uses Internet Explorer's engine.
MIN_WEBVIEW2 = (86, 0, 622, 0)
MIN_NET_RELEASE = 394802           # .NET Framework 4.6.2
# WebView2's EdgeUpdate client ids: the runtime, then Edge Beta, Dev and Canary.
WEBVIEW2_CLIENTS = (
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",
)

MB_OK, MB_YESNO, IDYES = 0x0, 0x4, 6
MB_ICONINFORMATION, MB_SETFOREGROUND = 0x40, 0x10000

MESSAGES = {
    "webview2": (
        "BioManager's window needs Microsoft Edge WebView2 Runtime, a free part "
        "of Windows from Microsoft. Windows 11 includes it; this computer "
        "doesn't have it yet.\n\n"
        "Yes: download it from Microsoft now. Run what downloads, then open "
        "BioManager again and it opens in its own window.\n"
        "No: not now.\n\n"
        "Either way, BioManager opens in your web browser meanwhile."
    ),
    "net": (
        "BioManager's window needs .NET Framework 4.6.2 or later, which this "
        "computer doesn't have. Windows Update installs it (Settings → Update "
        "& Security → Windows Update).\n\n"
        "Meanwhile, BioManager opens in your web browser."
    ),
    "failed": (
        "BioManager's window couldn't open:\n\n{error}\n\n"
        "It opens in your web browser instead."
    ),
}


def _registry(root: str, path: str, name: str):
    """A registry value, or None."""
    import winreg
    try:
        with winreg.OpenKey(getattr(winreg, root), path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _version(text) -> tuple:
    try:
        return tuple(int(part) for part in str(text).split("."))
    except ValueError:
        return ()


def missing(read=_registry, is_64bit: bool | None = None) -> str | None:
    """What the window lacks on this computer ("net" or "webview2"), or None."""
    if is_64bit is None:
        is_64bit = platform.machine().lower() != "x86"
    release = read("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full", "Release")
    if not isinstance(release, int) or release < MIN_NET_RELEASE:
        return "net"
    for client in WEBVIEW2_CLIENTS:
        for root in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE"):
            wow = "WOW6432Node\\" if root == "HKEY_LOCAL_MACHINE" and is_64bit else ""
            build = read(root, rf"SOFTWARE\{wow}Microsoft\EdgeUpdate\Clients\{client}", "pv")
            if build and _version(build) >= MIN_WEBVIEW2:
                return None
    return "webview2"


def unblock(root: Path) -> int:
    """Remove the came-from-the-internet mark from the DLLs under `root` (the
    bundle's own folder). Returns how many had it."""
    count = 0
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".dll"):
                try:
                    os.remove(os.path.join(folder, name) + ":Zone.Identifier")
                    count += 1
                except OSError:
                    pass
    return count


def _message(text: str, buttons: int) -> int:
    import ctypes
    return ctypes.windll.user32.MessageBoxW(None, text, "BioManager", buttons | MB_ICONINFORMATION | MB_SETFOREGROUND)


def run_in_browser(url: str, reason: str, error: BaseException | None = None, message=_message) -> None:
    """Say why there is no window, open the app in the web browser, and keep it
    running until the last message is closed."""
    if reason == "webview2":
        if message(MESSAGES["webview2"], MB_YESNO) == IDYES:
            webbrowser.open(WEBVIEW2_DOWNLOAD)
    else:
        message(MESSAGES[reason].format(error=str(error or "")[:400]), MB_OK)
    webbrowser.open(url)
    message(f"BioManager is open in your web browser at {url}\n\n"
            "Leave this message open while you use it: OK closes BioManager.", MB_OK)
