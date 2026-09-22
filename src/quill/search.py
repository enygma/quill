"""Search utilities: plain text, fuzzy, and date/time search over notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rapidfuzz import fuzz

from .models import Note, parse_dt


@dataclass
class SearchResult:
    note: Note
    score: float
    snippet: str = ""


def _make_snippet(text: str, query: str, radius: int = 40) -> str:
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return text[:80].replace("\n", " ")
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return (prefix + text[start:end] + suffix).replace("\n", " ")


def text_search(notes: list[Note], query: str) -> list[SearchResult]:
    """Case-insensitive substring search over title and body."""
    query = query.strip()
    if not query:
        return []
    results = []
    q_lower = query.lower()
    for note in notes:
        haystack = f"{note.title}\n{note.body}"
        if q_lower in haystack.lower():
            score = 100.0 if q_lower in note.title.lower() else 80.0
            results.append(SearchResult(note=note, score=score, snippet=_make_snippet(note.body or note.title, query)))
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def fuzzy_search(notes: list[Note], query: str, threshold: float = 55.0) -> list[SearchResult]:
    """Fuzzy match query against note titles (and lightly against body)."""
    query = query.strip()
    if not query:
        return []
    results = []
    for note in notes:
        title_score = fuzz.WRatio(query, note.title)
        body_score = fuzz.partial_ratio(query, note.body) if note.body else 0
        score = max(title_score, body_score * 0.9)
        if score >= threshold:
            results.append(SearchResult(note=note, score=score, snippet=_make_snippet(note.body or note.title, query)))
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def tag_search(notes: list[Note], tag: str) -> list[SearchResult]:
    """Notes carrying the given tag (case-insensitive, a leading '#' is
    optional), sorted by title."""
    tag_norm = tag.strip().lstrip("#").lower()
    if not tag_norm:
        return []
    results = [
        SearchResult(note=note, score=100.0)
        for note in notes
        if tag_norm in {t.lower() for t in note.tags}
    ]
    results.sort(key=lambda r: r.note.title.lower())
    return results


def all_tags(notes: list[Note]) -> list[str]:
    """Every distinct tag in use, sorted, for autocomplete/filtering."""
    seen: dict[str, str] = {}  # lowercase -> first-seen original casing
    for note in notes:
        for tag in note.tags:
            seen.setdefault(tag.lower(), tag)
    return sorted(seen.values(), key=str.lower)


def date_search(
    notes: list[Note],
    on: datetime | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    field: str = "updated",
) -> list[SearchResult]:
    """Search notes by created/updated date, either an exact day or a range."""
    results = []
    for note in notes:
        value = getattr(note, field, None)
        dt = parse_dt(value) if isinstance(value, str) else value
        if dt is None:
            continue
        if on is not None:
            if dt.date() != on.date():
                continue
        else:
            if since is not None and dt < since:
                continue
            if until is not None and dt > until:
                continue
        results.append(SearchResult(note=note, score=0.0))
    results.sort(key=lambda r: getattr(r.note, field), reverse=True)
    return results


def parse_date_query(text: str) -> datetime | None:
    """Best-effort parse of a user-typed date like 2026-09-21 or 2026-09-21 10:00."""
    text = text.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
