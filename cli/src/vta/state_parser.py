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


# ---------------------------------------------------------------------------
# View-tree search — find bounds by id, text, or class name from VTA state
# ---------------------------------------------------------------------------

def _match_view(node: dict, target: str) -> bool:
    """Check if a view node matches the target (by id, text, or class name)."""
    if node.get("id") and node["id"] == target:
        return True
    if node.get("text") and node["text"] == target:
        return True
    if node.get("class") and node["class"] == target:
        return True
    # Label nodes (non-interactive text embedded in tree)
    if node.get("type") == "label" and node.get("text") == target:
        return True
    return False


def find_view_bounds(state: dict, target: str, index: int = 0) -> list[int] | None:
    """Search the VTA state tree for a view by id, text, or class name.

    Returns ``[left, top, right, bottom]`` of the nth match (0-based index),
    or None if not found.  Uses the *clickable* ancestor's bounds when the
    matched node is a non-clickable label — this is essential for
    ExpandableListView group headers and Lynx-rendered elements.
    """
    actions = state.get("data", {}).get("actions", [])
    found = _search_tree(actions, target, index, [0])
    if found is None:
        return None
    bounds = found.get("bounds", [])
    if not bounds or len(bounds) < 4:
        return None
    return [int(v) for v in bounds[:4]]


def _search_tree(nodes: list[dict], target: str, want_index: int,
                 counter: list[int]) -> dict | None:
    """Recursively walk the action tree looking for the nth match."""
    for node in nodes:
        if _match_view(node, target):
            if counter[0] == want_index:
                # If this is a non-clickable label, try to use parent bounds
                if node.get("type") == "label":
                    return node
                return node
            counter[0] += 1
        children = node.get("children")
        if children:
            result = _search_tree(children, target, want_index, counter)
            if result is not None:
                return result
    return None


def center_of(bounds: list[int]) -> tuple[int, int]:
    """Return the (x, y) center pixel coordinates of a bounding box."""
    return ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)
