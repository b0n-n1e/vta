"""Post-install: register VTA skill for AI agent discovery."""

import os
import shutil
from pathlib import Path


def _install_skill() -> None:
    """Place SKILL.md where agents (Claude Code, etc.) auto-discover it."""
    skill_dir = Path.home() / ".claude" / "skills" / "vta"
    skill_dir.mkdir(parents=True, exist_ok=True)

    src = Path(__file__).parent / "resources" / "SKILL.md"
    dst = skill_dir / "SKILL.md"

    if dst.exists():
        print(f"vta: skill already installed at {dst}")
        return

    shutil.copy2(src, dst)
    print(f"vta: skill installed at {dst}")


if __name__ == "__main__":
    _install_skill()
