"""CLI entry point for the vta (View-to-Agent) tool.

Provides subcommands that communicate with the Companion App on an Android
device via adb. Each command prints JSON to stdout following the standard
response format: {"ok": true, "data": {...}} or {"ok": false, "error": "..."}.
"""

import argparse
import json
import os
import sys
import tempfile
from typing import Optional

from .adb_bridge import (
    URI_STATE,
    content_query,
    execute_insert,
    adb_shell,
    adb_install,
    adb_pull,
    adb_screencap,
    adb_start_activity,
    adb_force_stop,
    check_adb_available,
)
from .state_parser import parse_cursor_output, parse_state_response, find_view_bounds, center_of
from .models import Response


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def _ok(data: Optional[dict] = None) -> str:
    """Return a success JSON response."""
    return json.dumps(Response(ok=True, data=data).to_dict(), ensure_ascii=False)


def _err(message: str) -> str:
    """Return an error JSON response."""
    return json.dumps(Response(ok=False, error=message).to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Guard: ensure adb + device are available
# ---------------------------------------------------------------------------

def _require_device() -> None:
    """Exit with an error if adb is not available or no device is connected."""
    if not check_adb_available():
        print(_err("adb not available or no device connected"), file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_state() -> str:
    """vta state — query the current UI Action Space."""
    _require_device()
    from . import adb_bridge
    raw = content_query(adb_bridge.URI_STATE)
    result = parse_state_response(raw)
    return json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Core actions — all go through adb shell input (real touch pipeline).
# The SDK is only used for ViewTree capture.
# ---------------------------------------------------------------------------

def _get_state() -> dict:
    """Fetch the current UI state from the SDK."""
    from . import adb_bridge
    raw = content_query(adb_bridge.URI_STATE)
    return parse_state_response(raw)


def cmd_click(target: str, index: int | None = None) -> str:
    """vta click <target> [--index <n>] — click by id/text/class via real touch.

    Fetches the current ViewTree from the SDK, resolves the target to screen
    coordinates, then injects a tap through ``adb shell input tap`` — the full
    system input pipeline.  No performClick(), no ContentProvider round-trip.
    """
    _require_device()
    idx = index if index is not None else 0
    state = _get_state()
    bounds = find_view_bounds(state, target, idx)
    if bounds is None:
        return _err(f"View not found: {target} (index={idx})")
    x, y = center_of(bounds)
    try:
        adb_shell(["input", "tap", str(x), str(y)])
    except SystemExit:
        sys.exit(1)
    return _ok({"clicked": target, "index": idx, "coords": [x, y], "bounds": bounds})


def cmd_click_text(text: str, index: int | None = None) -> str:
    """vta click-text <text> [--index <n>] — click by visible text via real touch."""
    _require_device()
    idx = index if index is not None else 0
    state = _get_state()
    bounds = find_view_bounds(state, text, idx)
    if bounds is None:
        return _err(f"View with text '{text}' not found (index={idx})")
    x, y = center_of(bounds)
    try:
        adb_shell(["input", "tap", str(x), str(y)])
    except SystemExit:
        sys.exit(1)
    return _ok({"clicked": text, "index": idx, "coords": [x, y], "bounds": bounds})


def cmd_input(target: str, text: str) -> str:
    """vta input <target> <text> — enter text into an input field via SDK."""
    _require_device()
    raw = execute_insert("input", target=target, text=text)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_scroll(target: str, direction: str, index: int = 0) -> str:
    """vta scroll <target> <direction> — scroll via real swipe gesture.

    Computes a swipe path across the target view's bounds and injects it
    through ``adb shell input swipe``.
    """
    _require_device()
    direction = direction.lower()
    if direction not in ("up", "down", "left", "right"):
        return _err(f"Invalid direction: {direction}. Must be up, down, left, or right.")
    state = _get_state()
    bounds = find_view_bounds(state, target, index)
    if bounds is None:
        return _err(f"Scroll target not found: {target} (index={index})")

    l, t, r, b = bounds
    cx, cy = center_of(bounds)
    margin = min((r - l) // 5, (b - t) // 5, 200)
    # Swipe: finger moves opposite to scroll direction
    if direction == "up":
        x1 = cx; y1 = cy + margin; x2 = cx; y2 = cy - margin
    elif direction == "down":
        x1 = cx; y1 = cy - margin; x2 = cx; y2 = cy + margin
    elif direction == "left":
        x1 = cx + margin; y1 = cy; x2 = cx - margin; y2 = cy
    else:  # right
        x1 = cx - margin; y1 = cy; x2 = cx + margin; y2 = cy

    try:
        adb_shell(["input", "swipe", str(x1), str(y1), str(x2), str(y2), "300"])
    except SystemExit:
        sys.exit(1)
    return _ok({
        "scrolled": target,
        "direction": direction,
        "from": [x1, y1],
        "to": [x2, y2],
    })


def cmd_scroll_to(target: str, position: int) -> str:
    """vta scroll-to <target> <position> — scroll RecyclerView to exact position."""
    _require_device()
    raw = execute_insert("scroll_to", target=target, position=position)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_tap(x: int, y: int) -> str:
    """vta tap <x> <y> — inject a real touch event at screen coordinates.

    Uses ``adb shell input tap`` which goes through the full
    system input pipeline (MotionEvent dispatch), avoiding issues
    with performClick() on ExpandableListView groups, LynxViews, etc.
    """
    _require_device()
    try:
        adb_shell(["input", "tap", str(x), str(y)])
        return _ok({"tapped": [x, y]})
    except SystemExit:
        sys.exit(1)


def cmd_swipe(x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> str:
    """vta swipe <x1> <y1> <x2> <y2> [--duration <ms>] — inject a swipe gesture.

    Uses ``adb shell input swipe`` which dispatches real MotionEvents
    (ACTION_DOWN → ACTION_MOVE… → ACTION_UP), avoiding the UI state
    corruption caused by programmatic scrollBy().
    """
    _require_device()
    try:
        adb_shell(["input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])
        return _ok({"swiped": [x1, y1, x2, y2], "duration_ms": duration})
    except SystemExit:
        sys.exit(1)


def cmd_back() -> str:
    """vta back — press the Android back button."""
    _require_device()
    raw = execute_insert("back")
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_screenshot(output_dir: Optional[str] = None) -> str:
    """vta screenshot — take a screenshot via SDK and pull to local.

    Flow:
    1. Ask SDK for the target path via execute_insert("screenshot")
    2. Run adb shell screencap (needs shell permissions, not available to app process)
    3. adb pull to local
    """
    _require_device()
    # Step 1: get target path from SDK
    raw = execute_insert("screenshot")
    result = parse_cursor_output(raw)
    if result.get("result") != "ok":
        return json.dumps(result, ensure_ascii=False)
    remote_path = result.get("path", "/data/local/tmp/vta_screenshot.png")

    # Step 2: determine local path
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        local_path = os.path.join(output_dir, "screenshot.png")
    else:
        fd, local_path = tempfile.mkstemp(suffix=".png", prefix="vta_screenshot_")
        os.close(fd)

    # Step 3: run screencap on device (adb shell has framebuffer permission)
    # Step 4: pull to local
    try:
        adb_shell(["screencap", "-p", remote_path])
        result_path = adb_pull(remote_path, local_path)
        return _ok({"path": result_path})
    except SystemExit:
        sys.exit(1)
    except Exception as e:
        return _err(f"screenshot failed: {e}")


def cmd_wait(timeout_ms: int = 5000) -> str:
    """vta wait [-t <ms>] — wait for UI stability, then return state."""
    _require_device()
    raw = execute_insert("wait", timeout_ms=timeout_ms)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_watch(timeout_sec: int = 30, interval_ms: int = 1000) -> str:
    """vta watch — poll UI continuously, output each snapshot as NDJSON.

    Each line is a JSON snapshot. The Agent reads lines and decides when to act.
    Does NOT wait for stability — useful for auto-playing galleries, live AI responses.
    """
    _require_device()
    import time

    from . import adb_bridge
    from .state_parser import parse_state_response

    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        raw = content_query(adb_bridge.URI_STATE)
        cur = parse_state_response(raw)
        cur["watch"] = {"elapsed_ms": int((deadline - timeout_sec + (timeout_sec - (deadline - time.time()))) * 1000)}
        print(json.dumps(cur, ensure_ascii=False), flush=True)
        time.sleep(interval_ms / 1000.0)


def cmd_diff(timeout_sec: int = 10, interval_ms: int = 800) -> str:
    """vta diff — wait for UI content to change, then show what changed."""
    _require_device()
    import time

    from . import adb_bridge
    from .state_parser import parse_state_response

    # Snapshot baseline
    raw = content_query(adb_bridge.URI_STATE)
    base = parse_state_response(raw)
    base_actions = base.get("data", {}).get("actions", [])
    base_fp = _fingerprint(base_actions)

    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        time.sleep(interval_ms / 1000.0)
        raw = content_query(adb_bridge.URI_STATE)
        cur = parse_state_response(raw)
        cur_actions = cur.get("data", {}).get("actions", [])
        cur_fp = _fingerprint(cur_actions)

        if cur_fp != base_fp:
            return json.dumps({
                "ok": True,
                "changed": True,
                "data": cur.get("data", {}),
                "diff": _compute_diff(base_actions, cur_actions)
            }, ensure_ascii=False)

    # No change — return current state
    raw = content_query(adb_bridge.URI_STATE)
    cur = parse_state_response(raw)
    return json.dumps({
        "ok": True,
        "changed": False,
        "data": cur.get("data", {}),
        "diff": {"added": [], "removed": [], "changed": []}
    }, ensure_ascii=False)


def _fingerprint(actions: list) -> str:
    """Lightweight structural fingerprint including label nodes."""
    parts = []
    for a in actions:
        parts.append(f"{a.get('id','')}|{a.get('type','')}|{a.get('text','')}|{a.get('enabled','')}")
        for c in a.get("children", []):
            parts.append(_fingerprint([c]))
    return ";".join(parts)


def _collect_ids(actions: list) -> set:
    ids = set()
    for a in actions:
        if a.get("id"): ids.add(a["id"])
        if a.get("text"): ids.add(f"text:{a['text']}")
        for d in a.get("descriptors", []):
            ids.add(f"desc:{d.get('text','')}")
        ids.update(_collect_ids(a.get("children", [])))
    return ids


def _compute_diff(base: list, cur: list) -> dict:
    base_ids = _collect_ids(base)
    cur_ids = _collect_ids(cur)
    added = [x for x in sorted(cur_ids - base_ids) if x]
    removed = [x for x in sorted(base_ids - cur_ids) if x]
    changed = []
    # Also detect text changes
    for a in cur:
        if a.get("text") and f"text:{a['text']}" not in base_ids:
            changed.append({"id": a.get("id", ""), "text": a["text"], "change": "new_text"})
    return {"added": added[:20], "removed": removed[:20], "changed": changed[:10]}


def cmd_health() -> str:
    """vta health — check if SDK is running and accessible."""
    _require_device()
    raw = execute_insert("health")
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_setup() -> str:
    """vta setup — guide user to integrate SDK.

    The SDK auto-initializes via ContentProvider when the host app starts.
    No manual setup needed — just add debugImplementation to the target app.
    """
    _require_device()
    return _ok({
        "message": (
            "VTA SDK auto-initializes via ContentProvider.\n"
            "To use:\n"
            "1. Add debugImplementation project(':sdk') to target app's build.gradle\n"
            "2. Build and install the target app\n"
            "3. Verify with: vta health"
        )
    })


# ---------------------------------------------------------------------------
# App subcommands
# ---------------------------------------------------------------------------

def cmd_app_install(apk_path: str) -> str:
    """vta app install <apk> — install an APK on the device."""
    _require_device()
    if not os.path.isfile(apk_path):
        return _err(f"APK file not found: {apk_path}")
    try:
        adb_install(apk_path)
        return _ok({"installed": apk_path})
    except SystemExit:
        sys.exit(1)


def cmd_app_launch(package: str, activity: Optional[str] = None) -> str:
    """vta app launch <package> [--activity <activity>] — launch an app."""
    _require_device()
    try:
        adb_start_activity(package, activity)
        return _ok({"launched": package, "activity": activity})
    except SystemExit:
        sys.exit(1)


def cmd_app_kill(package: str) -> str:
    """vta app kill <package> — force-stop an app."""
    _require_device()
    try:
        adb_force_stop(package)
        return _ok({"killed": package})
    except SystemExit:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the full argument parser for the vta CLI."""

    parser = argparse.ArgumentParser(
        prog="vta",
        description="CLI-first Android UI Agent — control Android apps via structured UI data.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="vta 0.2.4",
    )
    parser.add_argument(
        "-a", "--authority",
        help="ContentProvider authority (auto-detected from --package if not set)",
    )
    parser.add_argument(
        "-p", "--package", dest="app_package",
        help="Target app package (auto-derives authority as <package>.vta)",
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # vta state
    sub.add_parser("state", help="Get current UI Action Space as JSON")

    # vta click <target>
    p_click = sub.add_parser("click", help="Click an element by resource-id")
    p_click.add_argument("target", help="Element id, e.g. com.xxx:id/btn_send")
    p_click.add_argument("--index", type=int, default=None, help="Nth match (0-based) for duplicate ids")

    # vta click-text <text>
    p_click_text = sub.add_parser("click-text", help="Click an element by its visible text")
    p_click_text.add_argument("text", help="Visible text to match")
    p_click_text.add_argument("--index", type=int, default=None, help="Nth match (0-based) for duplicate text")

    # vta input <target> <text>
    p_input = sub.add_parser("input", help="Enter text into an input field")
    p_input.add_argument("target", help="Element id of the input field")
    p_input.add_argument("text", help="Text to enter")

    # vta scroll <target> <direction>
    p_scroll = sub.add_parser("scroll", help="Scroll a scrollable container")
    p_scroll.add_argument("target", help="Element id or class name of the scrollable container")
    p_scroll.add_argument("direction", help="Scroll direction: up, down, left, right")
    p_scroll.add_argument("--index", type=int, default=0, help="Nth match (0-based) for duplicate ids/classes")

    # vta scroll-to <target> <position>
    p_scroll_to = sub.add_parser("scroll-to", help="Scroll RecyclerView to exact position (requires SDK)")
    p_scroll_to.add_argument("target", help="Element id of the RecyclerView")
    p_scroll_to.add_argument("position", type=int, help="Adapter position to scroll to")

    # vta tap <x> <y>
    p_tap = sub.add_parser("tap", help="Inject a real touch event at screen coordinates (x y)")
    p_tap.add_argument("x", type=int, help="X coordinate on screen")
    p_tap.add_argument("y", type=int, help="Y coordinate on screen")

    # vta swipe <x1> <y1> <x2> <y2> [--duration <ms>]
    p_swipe = sub.add_parser("swipe", help="Inject a swipe gesture via real MotionEvents")
    p_swipe.add_argument("x1", type=int, help="Start X coordinate")
    p_swipe.add_argument("y1", type=int, help="Start Y coordinate")
    p_swipe.add_argument("x2", type=int, help="End X coordinate")
    p_swipe.add_argument("y2", type=int, help="End Y coordinate")
    p_swipe.add_argument(
        "--duration", "-d",
        type=int,
        default=300,
        metavar="MS",
        help="Swipe duration in milliseconds (default: 300)",
    )

    # vta back
    sub.add_parser("back", help="Press the Android back button")

    # vta screenshot
    p_screenshot = sub.add_parser("screenshot", help="Take a screenshot")
    p_screenshot.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Directory to save screenshot (default: temp file)",
    )

    # vta wait [-t <ms>]
    p_wait = sub.add_parser("wait", help="Wait for UI stability")
    p_wait.add_argument(
        "-t", "--timeout",
        type=int,
        default=5000,
        metavar="MS",
        help="Timeout in milliseconds (default: 5000)",
    )

    # vta watch [-t <sec>] [-i <ms>]
    p_watch = sub.add_parser("watch", help="Poll until UI content stops changing (for async AI responses)")
    p_watch.add_argument(
        "-t", "--timeout",
        type=int,
        default=30,
        metavar="SEC",
        help="Max wait time in seconds (default: 30)",
    )
    p_watch.add_argument(
        "-i", "--interval",
        type=int,
        default=1000,
        metavar="MS",
        help="Poll interval in milliseconds (default: 1000)",
    )

    # vta diff [-t <sec>] [-i <ms>]
    p_diff = sub.add_parser("diff", help="Wait for UI change and show what changed")
    p_diff.add_argument("-t", "--timeout", type=int, default=10, metavar="SEC",
                        help="Max wait time in seconds (default: 10)")
    p_diff.add_argument("-i", "--interval", type=int, default=800, metavar="MS",
                        help="Poll interval in milliseconds (default: 800)")

    # vta health

    # vta setup
    sub.add_parser("setup", help="Print integration guide")

    # vta install <subcommand>
    p_install = sub.add_parser("install", help="Post-install setup commands")
    install_sub = p_install.add_subparsers(dest="install_command", help="Install subcommands")
    install_sub.add_parser("skill", help="Register VTA skill for agent auto-discovery")

    # vta app <subcommand> ...
    p_app = sub.add_parser("app", help="App management commands")
    app_sub = p_app.add_subparsers(dest="app_command", help="App subcommands")

    # vta app install <apk>
    p_app_install = app_sub.add_parser("install", help="Install an APK")
    p_app_install.add_argument("apk", help="Path to the APK file")

    # vta app launch <package> [--activity <activity>]
    p_app_launch = app_sub.add_parser("launch", help="Launch an app")
    p_app_launch.add_argument("package", help="Package name, e.g. com.xt.retouch")
    p_app_launch.add_argument(
        "--activity", "-a",
        default=None,
        help="Activity class name (optional, resolves launcher activity if omitted)",
    )

    # vta app kill <package>
    p_app_kill = app_sub.add_parser("kill", help="Force-stop an app")
    p_app_kill.add_argument("package", help="Package name")

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> None:
    """Entry point for the vta CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    from . import adb_bridge as bridge

    if args.app_package:
        bridge.PROVIDER_AUTHORITY = f"{args.app_package}.vta"
    elif args.authority:
        bridge.PROVIDER_AUTHORITY = args.authority
    else:
        # Auto-detect from foreground app
        try:
            fg = adb_bridge.adb_shell(["dumpsys", "activity", "activities"])
            import re
            m = re.search(r"topResumedActivity=.*?/([^/\s]+)\s", fg)
            if m:
                bridge.PROVIDER_AUTHORITY = f"{m.group(1)}.vta"
            else:
                bridge.PROVIDER_AUTHORITY = "com.bonnie.vta"
        except Exception:
            bridge.PROVIDER_AUTHORITY = "com.bonnie.vta"

    bridge.URI_STATE = f"content://{bridge.PROVIDER_AUTHORITY}/state"
    bridge.URI_EXECUTE = f"content://{bridge.PROVIDER_AUTHORITY}/execute"
    bridge.URI_RESULT = f"content://{bridge.PROVIDER_AUTHORITY}/result"

    try:
        cmd = args.command
        if cmd == "state":
            result = cmd_state()
        elif cmd == "click":
            result = cmd_click(args.target, getattr(args, 'index', None))
        elif cmd == "click-text":
            result = cmd_click_text(args.text, getattr(args, 'index', None))
        elif cmd == "input":
            result = cmd_input(args.target, args.text)
        elif cmd == "scroll":
            result = cmd_scroll(args.target, args.direction, getattr(args, 'index', 0))
        elif cmd == "scroll-to":
            result = cmd_scroll_to(args.target, args.position)
        elif cmd == "back":
            result = cmd_back()
        elif cmd == "tap":
            result = cmd_tap(args.x, args.y)
        elif cmd == "swipe":
            result = cmd_swipe(args.x1, args.y1, args.x2, args.y2,
                              getattr(args, 'duration', 300))
        elif cmd == "screenshot":
            result = cmd_screenshot(args.output_dir)
        elif cmd == "wait":
            result = cmd_wait(args.timeout)
        elif cmd == "watch":
            cmd_watch(args.timeout, args.interval)
            return
        elif cmd == "diff":
            result = cmd_diff(args.timeout, args.interval)
        elif cmd == "health":
            result = cmd_health()
        elif cmd == "setup":
            result = cmd_setup()
        elif cmd == "install":
            if args.install_command == "skill":
                from .install import _install_skill
                _install_skill()
                result = _ok({"message": "Skill installed. Restart your agent session to pick it up."})
            else:
                result = _err("unknown install subcommand. Try: vta install skill")
        elif cmd == "app":
            if args.app_command is None:
                # Print help for the 'app' subcommand
                for action in parser._actions:
                    if action.dest == "app" and hasattr(action, "choices"):
                        for name, choice_parser in (action.choices or {}).items():
                            if name == "app":
                                choice_parser.print_help()
                                break
                result = ""
            elif args.app_command == "install":
                result = cmd_app_install(args.apk)
            elif args.app_command == "launch":
                result = cmd_app_launch(getattr(args, 'package', ''), getattr(args, 'activity', None))
            elif args.app_command == "kill":
                result = cmd_app_kill(getattr(args, 'package', ''))
            else:
                result = _err("unknown app subcommand: {}".format(args.app_command))
        else:
            result = _err("unknown command: {}".format(cmd))
    except KeyboardInterrupt:
        print(_err("interrupted"), file=sys.stderr)
        sys.exit(130)

    print(result)


if __name__ == "__main__":
    main()
