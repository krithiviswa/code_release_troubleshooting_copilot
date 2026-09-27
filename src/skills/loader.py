"""Load reusable local SKILL.md instructions."""
from functools import lru_cache
from pathlib import Path

from config import SKILLS_DIR


@lru_cache(maxsize=32)
def load_skill(skill_name: str) -> str:
    """Read one worker skill file.

    WHY: Keep reusable behavioral instructions outside Python code.
    NEXT: src/prompts/*.py -> the prompt that embeds the skill.
    """
    path = Path(SKILLS_DIR) / skill_name / "SKILL.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
