"""Note data model and Markdown frontmatter (de)serialization."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
ISO_FMT = "%Y-%m-%dT%H:%M:%S"


def now_iso() -> str:
    return datetime.now().strftime(ISO_FMT)


def parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, ISO_FMT)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


@dataclass
class Note:
    """A single note, backed by a Markdown file with YAML frontmatter."""

    path: Path  # absolute path on disk
    rel_path: str  # path relative to notes root, using '/' separators, no extension
    title: str
    body: str = ""
    created: str = field(default_factory=now_iso)
    updated: str = field(default_factory=now_iso)
    pinned: bool = False
    tags: list[str] = field(default_factory=list)

    @property
    def folder(self) -> str:
        parts = self.rel_path.split("/")
        return "/".join(parts[:-1])

    @property
    def filename(self) -> str:
        return self.path.name

    def to_markdown(self) -> str:
        frontmatter = {
            "title": self.title,
            "created": self.created,
            "updated": self.updated,
            "pinned": self.pinned,
            "tags": self.tags,
        }
        fm_text = yaml.safe_dump(frontmatter, sort_keys=False).strip()
        return f"---\n{fm_text}\n---\n\n{self.body.strip()}\n"

    @classmethod
    def from_file(cls, path: Path, root: Path) -> "Note":
        text = path.read_text(encoding="utf-8")
        rel_path = path.relative_to(root).with_suffix("").as_posix()
        match = FRONTMATTER_RE.match(text)
        if match:
            fm_text, body = match.groups()
            try:
                data = yaml.safe_load(fm_text) or {}
            except yaml.YAMLError:
                data = {}
        else:
            data = {}
            body = text
        title = data.get("title") or path.stem
        return cls(
            path=path,
            rel_path=rel_path,
            title=title,
            body=body.strip("\n"),
            created=str(data.get("created") or now_iso()),
            updated=str(data.get("updated") or now_iso()),
            pinned=bool(data.get("pinned", False)),
            tags=list(data.get("tags") or []),
        )

    def touch(self) -> None:
        self.updated = now_iso()
