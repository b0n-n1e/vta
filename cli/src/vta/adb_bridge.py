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
URI_A11Y = f"content://{PROVIDER_AUTHORITY}/a11y"


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


def adb_uiautomator_dump(timeout: int = 15) -> str:
    """Run uiautomator dump and return the XML content as a string.

    Falls back to /sdcard/vta_ui.xml if stdout is empty (some devices/ROMs
    write the XML only to the file, not to stdout).

    Usage:
        xml = adb_uiautomator_dump()
    """
    remote_path = "/sdcard/vta_ui.xml"
    try:
        _run_adb(["shell", "uiautomator", "dump", remote_path], timeout=timeout)
    except SystemExit:
        pass

    # Read the file off device
    try:
        result = subprocess.run(
            [ADB_BIN, "shell", "cat", remote_path],
            capture_output=True, text=True, timeout=timeout,
        )
        stdout = result.stdout.strip()
        if stdout and stdout.startswith("<?xml"):
            return stdout
    except Exception:
        pass

    return ""


def parse_uiautomator_xml(xml_string: str) -> list[dict]:
    """Parse uiautomator dump XML and return A11y nodes in the same format
    as the SDK's /a11y endpoint.

    Returns a list of node dicts with keys:
    class, text, content_desc, resource_id, clickable, focusable, scrollable,
    enabled, bounds, is_lynx, children
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_string)
    nodes: list[dict] = []

    def _parse_node(elem: ET.Element) -> dict | None:
        class_name = elem.get("class", "")
        text = elem.get("text", "")
        content_desc = elem.get("content-desc", "")
        bounds_str = elem.get("bounds", "")
        resource_id = elem.get("resource-id", "")

        display_text = content_desc if content_desc else text
        is_lynx = "lynx" in class_name.lower()

        node: dict = {
            "class": class_name,
            "text": display_text,
            "content_desc": content_desc,
            "resource_id": resource_id,
            "clickable": elem.get("clickable", "false") == "true",
            "focusable": elem.get("focusable", "false") == "true",
            "scrollable": elem.get("scrollable", "false") == "true",
            "enabled": elem.get("enabled", "true") == "true",
            "checked": elem.get("checked", "false") == "true",
            "selected": elem.get("selected", "false") == "true",
            "is_lynx": is_lynx,
        }

        # Parse bounds from "[l,t][r,b]" format
        bounds = _parse_bounds(bounds_str)
        if bounds:
            node["bounds"] = bounds

        # Recurse children
        children: list[dict] = []
        for child_elem in elem:
            parsed = _parse_node(child_elem)
            if parsed:
                children.append(parsed)
        if children:
            node["children"] = children

        return node

    for child in root:
        parsed = _parse_node(child)
        if parsed:
            nodes.append(parsed)

    return nodes


def _parse_bounds(bounds_str: str) -> list[int] | None:
    """Parse uiautomator bounds string like '[0,104][1440,244]'."""
    import re

    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
    if m:
        return [int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))]
    return None


def a11y_query(timeout: int = 15) -> dict:
    """Get A11y tree — Plan A: SDK /a11y endpoint, Plan B: uiautomator dump fallback.

    Returns:
        {"ok": true/false, "nodes": [...], "source": "sdk"|"uiautomator"}
    """
    # Plan A: try SDK /a11y endpoint
    try:
        raw = content_query(URI_A11Y, timeout=timeout)
    except SystemExit:
        raw = ""
    except Exception:
        raw = ""

    if raw:
        import json
        from .state_parser import parse_cursor_output
        try:
            result = parse_cursor_output(raw)
            if result.get("ok"):
                result["source"] = "sdk"
                return result
        except (json.JSONDecodeError, TypeError, SystemExit):
            pass

    # Plan B: uiautomator dump fallback
    xml_str = adb_uiautomator_dump(timeout=timeout)
    if xml_str:
        nodes = parse_uiautomator_xml(xml_str)
        return {"ok": True, "nodes": nodes, "source": "uiautomator"}

    return {"ok": False, "error": "both SDK a11y and uiautomator dump failed", "nodes": []}


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
