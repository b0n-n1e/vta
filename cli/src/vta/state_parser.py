"""Parser for ContentProvider cursor output format.

Parses the format returned by adb shell content query/insert:
    Row: 0 _json={"ok":true,"data":{...}}
"""

import json
import re
import sys

# Pattern: "Row: <N> _json=<JSON>"
# The JSON value may contain escaped quotes or nested objects.
_ROW_PATTERN = re.compile(r"^Row:\s*\d+\s+_json=(.+)$", re.MULTILINE)


def parse_cursor_output(raw: str) -> dict:
    """Parse ContentProvider cursor output into a Python dict.

    The expected format from the Companion App is:
        Row: 0 _json={"ok": true, "data": {...}}

    This function extracts the JSON payload from the _json= column and
    returns it as a dict.

    Args:
        raw: The raw stdout string from adb shell content query/insert.

    Returns:
        A dict parsed from the JSON payload.

    Raises:
        SystemExit: If the cursor output cannot be parsed.
    """
    raw = raw.strip()
    if not raw:
        print(
            '{"ok": false, "error": "empty response from device"}',
            file=sys.stderr,
        )
        sys.exit(1)

    match = _ROW_PATTERN.search(raw)
    if not match:
        # Fallback: try to parse the entire raw string as JSON directly
        # (some adb versions or providers may return plain JSON)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print(
                f'{{"ok": false, "error": "unexpected cursor output format: {raw[:200]}..."}}',
                file=sys.stderr,
            )
            sys.exit(1)

    json_str = match.group(1)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(
            f'{{"ok": false, "error": "failed to parse JSON from cursor: {e}"}}',
            file=sys.stderr,
        )
        sys.exit(1)


def parse_state_response(raw: str) -> dict:
    """Parse the /state query response, extracting the Action Space data.

    This wraps parse_cursor_output and validates the Response structure.
    """
    result = parse_cursor_output(raw)
    if not isinstance(result, dict):
        print(
            '{"ok": false, "error": "parsed state is not a dict"}',
            file=sys.stderr,
        )
        sys.exit(1)
    return result


def parse_execute_response(raw: str) -> dict:
    """Parse the /execute insert response, extracting the execution result.

    Similar to parse_state_response but specific to execute output.
    """
    result = parse_cursor_output(raw)
    if not isinstance(result, dict):
        print(
            '{"ok": false, "error": "parsed execute result is not a dict"}',
            file=sys.stderr,
        )
        sys.exit(1)
    return result
