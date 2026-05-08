"""ADB communication layer — wraps adb shell content query/insert calls."""

from __future__ import annotations

import subprocess
import sys
from urllib.parse import quote


ADB_BIN = "adb"

# ContentProvider authority as defined in PLAN.md section 5.2
PROVIDER_AUTHORITY = "com.bonnie.vta"
URI_STATE = f"content://{PROVIDER_AUTHORITY}/state"
URI_EXECUTE = f"content://{PROVIDER_AUTHORITY}/execute"
URI_RESULT = f"content://{PROVIDER_AUTHORITY}/result"


def _run_adb(args: list[str], timeout: int = 15) -> str:
    """Run an adb command and return stripped stdout.

    Raises subprocess.CalledProcessError on non-zero exit.
    """
    cmd = [ADB_BIN] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        print(
            '{"ok": false, "error": "adb not found. Is Android SDK platform-tools installed and on PATH?"}',
            file=sys.stderr,
        )
        sys.exit(1)

    if result.returncode != 0:
        # Include both stdout and stderr in the error message for debugging
        stderr = result.stderr.strip() if result.stderr else ""
        stdout = result.stdout.strip() if result.stdout else ""
        detail = stderr or stdout or "unknown error"
        print(
            f'{{"ok": false, "error": "adb command failed: {detail}"}}',
            file=sys.stderr,
        )
        sys.exit(1)

    return result.stdout.strip()


def content_query(uri: str, timeout: int = 15) -> str:
    """Execute an adb shell content query and return the raw stdout.

    Quotes the URI to prevent & from being interpreted as shell command
    separator on the device side.

    Usage:
        raw = content_query("content://com.bonnie.vta/state")
    """
    return _run_adb(["shell", f"content query --uri '{uri}'"], timeout=timeout)


def execute_insert(action: str, target: str | None = None, text: str | None = None,
                   direction: str | None = None, position: int | None = None,
                   index: int | None = None,
                   timeout_ms: int = 5000, timeout: int = 15) -> str:
    """Execute an action via content query with URI query parameters.

    Uses query() on /execute?action=...&target=... to avoid the colon-in-bind
    issue with content insert when target IDs contain colons (e.g. android:id/btn).

    The SDK's UIAgentProvider.query() handles /execute by reading params from
    the URI and returning a cursor with _json column.

    Usage:
        raw = execute_insert("click", target="android:id/button1")
    """
    params = [f"action={quote(action, safe='')}"]
    if target:
        params.append(f"target={quote(target, safe='')}")
    if text:
        params.append(f"text={quote(text, safe='')}")
    if direction:
        params.append(f"direction={quote(direction, safe='')}")
    if position is not None:
        params.append(f"position={position}")
    if index is not None:
        params.append(f"index={index}")
    params.append(f"timeout_ms={timeout_ms}")

    uri = f"{URI_EXECUTE}?{'&'.join(params)}"
    return content_query(uri, timeout=timeout)


def adb_pull(remote_path: str, local_path: str, timeout: int = 15) -> str:
    """Pull a file from device to local machine.

    Usage:
        local = adb_pull("/sdcard/vta_screenshot.png", "/tmp/out.png")
    Returns the local path on success.
    """
    _run_adb(["pull", remote_path, local_path], timeout=timeout)
    return local_path


def adb_shell(cmd: list[str], timeout: int = 15) -> str:
    """Run an arbitrary adb shell command and return stdout.

    Usage:
        out = adb_shell(["input", "keyevent", "KEYCODE_BACK"])
    """
    return _run_adb(["shell"] + cmd, timeout=timeout)


def adb_install(apk_path: str, timeout: int = 120) -> str:
    """Install an APK on the device.

    Usage:
        out = adb_install("/path/to/companion.apk")
    """
    return _run_adb(["install", "-r", apk_path], timeout=timeout)


def adb_screencap(output_path: str, timeout: int = 15) -> str:
    """Take a screenshot and pull it to the local machine.

    Usage:
        path = adb_screencap("/tmp/screenshot.png")
    Returns the local path on success.
    """
    remote_path = "/sdcard/vta_screenshot.png"
    _run_adb(["shell", "screencap", "-p", remote_path], timeout=timeout)
    _run_adb(["pull", remote_path, output_path], timeout=timeout)
    _run_adb(["shell", "rm", remote_path], timeout=5)
    return output_path


def adb_start_activity(package: str, activity = None, timeout: int = 15) -> str:
    """Launch an app by package name (and optionally activity).

    Usage:
        adb_start_activity("com.xt.retouch")
    """
    if activity:
        component = f"{package}/{activity}"
    else:
        # Let the launcher resolve the main activity
        component = package
    return _run_adb(
        ["shell", "am", "start", "-n", component],
        timeout=timeout,
    )


def adb_force_stop(package: str, timeout: int = 15) -> str:
    """Force-stop an app by package name.

    Usage:
        adb_force_stop("com.xt.retouch")
    """
    return _run_adb(["shell", "am", "force-stop", package], timeout=timeout)


def adb_grant_permission(package: str, permission: str, timeout: int = 15) -> str:
    """Grant a permission to a package.

    Usage:
        adb_grant_permission("com.bonnie.vta", "android.permission.SYSTEM_ALERT_WINDOW")
    """
    return _run_adb(
        ["shell", "pm", "grant", package, permission],
        timeout=timeout,
    )


def check_adb_available() -> bool:
    """Check whether adb is available and a device is connected."""
    try:
        result = subprocess.run(
            [ADB_BIN, "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        # First line: "List of devices attached"
        # Subsequent lines: "<serial>\tdevice" or "<serial>\toffline"
        devices = [
            line.split("\t")[0]
            for line in lines[1:]
            if line.strip() and "\tdevice" in line
        ]
        return len(devices) > 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
