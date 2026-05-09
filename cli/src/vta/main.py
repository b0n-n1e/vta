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
from .state_parser import parse_cursor_output, parse_state_response
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


def cmd_click(target: str, index: int | None = None) -> str:
    """vta click <target> [--index <n>] — click an element by id (optionally nth match)."""
    _require_device()
    raw = execute_insert("click", target=target, index=index)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_click_text(text: str, index: int | None = None) -> str:
    """vta click-text <text> [--index <n>] — click an element by text (optionally nth match)."""
    _require_device()
    raw = execute_insert("click_text", text=text, index=index)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_input(target: str, text: str) -> str:
    """vta input <target> <text> — enter text into an input field."""
    _require_device()
    raw = execute_insert("input", target=target, text=text)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_scroll(target: str, direction: str) -> str:
    """vta scroll <target> <direction> — scroll a scrollable container."""
    _require_device()
    direction = direction.lower()
    if direction not in ("up", "down", "left", "right"):
        return _err(f"invalid direction: {direction}. Must be up, down, left, or right.")
    raw = execute_insert("scroll", target=target, direction=direction)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


def cmd_scroll_to(target: str, position: int) -> str:
    """vta scroll-to <target> <position> — scroll RecyclerView to exact position."""
    _require_device()
    raw = execute_insert("scroll_to", target=target, position=position)
    result = parse_cursor_output(raw)
    return json.dumps(result, ensure_ascii=False)


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
        version="vta 0.1.0",
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
    p_scroll.add_argument("target", help="Element id of the scrollable container")
    p_scroll.add_argument("direction", help="Scroll direction: up, down, left, right")

    # vta scroll-to <target> <position>
    p_scroll_to = sub.add_parser("scroll-to", help="Scroll RecyclerView to exact position (requires SDK)")
    p_scroll_to.add_argument("target", help="Element id of the RecyclerView")
    p_scroll_to.add_argument("position", type=int, help="Adapter position to scroll to")

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

    # vta health
    sub.add_parser("health", help="Check Companion App status")

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
            result = cmd_scroll(args.target, args.direction)
        elif cmd == "scroll-to":
            result = cmd_scroll_to(args.target, args.position)
        elif cmd == "back":
            result = cmd_back()
        elif cmd == "screenshot":
            result = cmd_screenshot(args.output_dir)
        elif cmd == "wait":
            result = cmd_wait(args.timeout)
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
