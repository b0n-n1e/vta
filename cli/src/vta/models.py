"""Data models for UIAgent Action Space and commands.

Matches the JSON schema defined in PLAN.md section 4.1.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class Resolution:
    """Screen resolution."""
    width: int
    height: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AdapterInfo:
    """RecyclerView adapter metadata (only available when SDK is integrated)."""
    total_items: int
    visible_range: list[int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Action:
    """A single interactable UI element in the Action Space."""

    id: str
    type: str  # clickable, editable, scrollable
    label: str = ""
    hint: str = ""
    class_: str = field(default="", metadata={"json_key": "class"})
    bounds: list[int] = field(default_factory=list)
    enabled: bool = True

    # Optional fields
    index: Optional[int] = None
    visibility: str = "visible"  # "visible", "invisible", "gone"
    alpha: Optional[float] = None
    focused: bool = False
    text: Optional[str] = None
    scroll_direction: Optional[str] = None  # "vertical" or "horizontal"
    adapter_info: Optional[AdapterInfo] = None
    children: Optional[list["Action"]] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "hint": self.hint,
            "class": self.class_,
            "bounds": self.bounds,
            "enabled": self.enabled,
            "visibility": self.visibility,
            "focused": self.focused,
        }
        if self.index is not None:
            d["index"] = self.index
        if self.alpha is not None:
            d["alpha"] = self.alpha
        if self.text is not None:
            d["text"] = self.text
        if self.scroll_direction is not None:
            d["scroll_direction"] = self.scroll_direction
        if self.adapter_info is not None:
            d["adapter_info"] = self.adapter_info.to_dict()
        if self.children is not None:
            d["children"] = [c.to_dict() for c in self.children]
        return d


@dataclass
class DialogInfo:
    """A detected dialog or popup on screen."""
    title: str = ""
    message: str = ""
    type: str = ""  # "dialog", "popup", "toast"
    has_positive: bool = False
    positive_text: str = ""
    has_negative: bool = False
    negative_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ActionSpace:
    """The full UI Action Space returned by vta state."""

    package: str = ""
    activity: str = ""
    stable: bool = False
    resolution: Optional[Resolution] = None
    actions: list[Action] = field(default_factory=list)
    dialogs: list[DialogInfo] = field(default_factory=list)
    toasts: list[DialogInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "package": self.package,
            "activity": self.activity,
            "stable": self.stable,
        }
        if self.resolution is not None:
            d["resolution"] = self.resolution.to_dict()
        d["actions"] = [a.to_dict() for a in self.actions]
        d["dialogs"] = [dlg.to_dict() for dlg in self.dialogs]
        d["toasts"] = [t.to_dict() for t in self.toasts]
        return d


@dataclass
class ExecuteResult:
    """Result of an execute action (click, input, scroll, etc.)."""
    result: str = "ok"  # "ok" or "error"
    message: str = ""
    new_state: Optional[ActionSpace] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"result": self.result, "message": self.message}
        if self.new_state is not None:
            d["new_state"] = self.new_state.to_dict()
        return d


@dataclass
class Response:
    """Standard response wrapper for all CLI commands."""
    ok: bool
    data: Optional[dict] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"ok": self.ok}
        if self.data is not None:
            d["data"] = self.data
        if self.error is not None:
            d["error"] = self.error
        return d


@dataclass
class AgentCommand:
    """Command sent to the Companion App via ContentProvider insert."""

    action: str  # click, input, scroll, scroll_to, back, screenshot, wait
    target: Optional[str] = None
    text: Optional[str] = None
    direction: Optional[str] = None
    position: Optional[int] = None
    index: Optional[int] = None
    timeout_ms: Optional[int] = None

    def to_bind_args(self) -> list[tuple[str, str]]:
        """Convert to (key, typed_value) pairs for adb content insert --bind args.

        Returns list of (key, typed_value) where typed_value is like 's:hello' or 'i:42'.
        """
        binds: list[tuple[str, str]] = []
        binds.append(("action", f"s:{self.action}"))
        if self.target:
            binds.append(("target", f"s:{self.target}"))
        if self.text:
            binds.append(("text", f"s:{self.text}"))
        if self.direction:
            binds.append(("direction", f"s:{self.direction}"))
        if self.position is not None:
            binds.append(("position", f"i:{self.position}"))
        if self.index is not None:
            binds.append(("index", f"i:{self.index}"))
        if self.timeout_ms is not None:
            binds.append(("timeout_ms", f"i:{self.timeout_ms}"))
        return binds
