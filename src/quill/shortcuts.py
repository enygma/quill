"""Live text-expansion shortcuts for the editor.

Typing a complete `{name}` or `{name:args}` pattern expands it in place --
e.g. `{table:2,3}` becomes a 2-column, 3-row Markdown table skeleton.
Two built-ins ('table', 'template') plus any number of user-defined custom
shortcuts (a fixed name -> replacement text mapping, managed via
`quill shortcuts` or the Settings screen).
"""

from __future__ import annotations

import re
from collections.abc import Callable

# A complete shortcut ending exactly at the cursor -- e.g. in "before {table:2,3}",
# matches "{table:2,3}" with name="table", args="2,3".
SHORTCUT_RE = re.compile(r"\{(\w+)(?::([^{}]*))?\}$")

BUILTIN_NAMES = ("table", "template")


def find_completed_shortcut(text_before_cursor: str) -> re.Match[str] | None:
    """If the text just before the cursor ends with a complete shortcut,
    return the match (name is group 1, args is group 2 or None); else None."""
    return SHORTCUT_RE.search(text_before_cursor)


def build_table(args: str) -> str | None:
    """'{table:cols,rows}' -> a Markdown table skeleton. rows defaults to 1.
    None (leaving the typed text alone) if cols/rows aren't valid numbers.
    """
    parts = [p.strip() for p in args.split(",")] if args else []
    if not parts or not parts[0]:
        return None
    try:
        cols = int(parts[0])
        rows = int(parts[1]) if len(parts) > 1 and parts[1] else 1
    except ValueError:
        return None
    if cols < 1 or rows < 0:
        return None

    header = "| " + " | ".join(f"Column {i + 1}" for i in range(cols)) + " |"
    divider = "|" + "|".join(" --- " for _ in range(cols)) + "|"
    if rows == 0:
        return f"{header}\n{divider}"
    body = "\n".join("| " + " | ".join("" for _ in range(cols)) + " |" for _ in range(rows))
    return f"{header}\n{divider}\n{body}"


def expand_shortcut(
    name: str,
    args: str,
    *,
    resolve_template: Callable[[str], str | None],
    custom_shortcuts: dict[str, str],
) -> str | None:
    """The expansion text for a shortcut, or None if it doesn't match
    anything known (in which case the typed text is left as-is)."""
    if name == "table":
        return build_table(args)
    if name == "template":
        return resolve_template(args.strip())
    if not args and name in custom_shortcuts:
        return custom_shortcuts[name]
    return None
