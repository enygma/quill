"""Wiki-style [[note]] link parsing and autocomplete support."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

WIKILINK_RE = re.compile(r"\[\[([^\[\]]*)\]\]")

# [[Target]] or [[Target|Custom Label]]
FULL_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]")

WIKI_SCHEME = "wiki:"

# Matches an *unclosed* [[ that the cursor is currently typing inside,
# e.g. "See [[proj" -> capture group "proj"
OPEN_WIKILINK_RE = re.compile(r"\[\[([^\[\]]*)$")


def find_links(text: str) -> list[str]:
    """Return all wiki-link targets referenced in text."""
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text) if m.group(1).strip()]


def find_link_targets(text: str) -> list[tuple[str, str]]:
    """Return (target, label) pairs for every [[wiki link]] in text, in
    first-seen order, deduplicated by target. Used for keyboard navigation
    to a note's linked notes."""
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for match in FULL_WIKILINK_RE.finditer(text):
        target = match.group(1).strip()
        label = (match.group(2) or target).strip()
        if target and target not in seen:
            seen.add(target)
            results.append((target, label))
    return results


def find_open_link(text_before_cursor: str) -> str | None:
    """If the cursor is inside an unclosed [[ ... ]], return the partial text typed so far."""
    match = OPEN_WIKILINK_RE.search(text_before_cursor)
    if match:
        return match.group(1)
    return None


def render_for_preview(text: str) -> str:
    """Rewrite [[Target]] / [[Target|Label]] wiki-links into clickable Markdown
    links (using a custom `wiki:` scheme) so Textual's Markdown widget renders
    and emits click events for them.
    """

    def _sub(match: re.Match) -> str:
        target = match.group(1).strip()
        label = (match.group(2) or target).strip()
        return f"[{label}]({WIKI_SCHEME}{target})"

    return FULL_WIKILINK_RE.sub(_sub, text)


def is_wiki_href(href: str) -> str | None:
    """Return the link target if href is a wiki: link, else None."""
    if href.startswith(WIKI_SCHEME):
        return href[len(WIKI_SCHEME):]
    return None


def suggest_titles(partial: str, titles: list[str], limit: int = 8) -> list[str]:
    """Narrow known note titles down to ones matching a partially-typed link
    target, e.g. "test n" -> "test note 1" but not "test 1".

    Titles containing `partial` as a substring are preferred (and are the
    only results shown, when any exist) so typing narrows the list rather
    than just re-ranking it. Fuzzy matching is only used as a fallback, to
    tolerate typos when nothing contains the typed text outright.
    """
    partial = partial.strip()
    if not partial:
        return sorted(titles)[:limit]

    partial_lower = partial.lower()
    substring_matches = [t for t in titles if partial_lower in t.lower()]
    if substring_matches:
        def sort_key(title: str) -> tuple[int, int, str]:
            lower = title.lower()
            starts_with = 0 if lower.startswith(partial_lower) else 1
            return (starts_with, lower.index(partial_lower), lower)

        substring_matches.sort(key=sort_key)
        return substring_matches[:limit]

    scored = [(fuzz.WRatio(partial, t), t) for t in titles]
    scored = [s for s in scored if s[0] > 60]
    scored.sort(key=lambda s: s[0], reverse=True)
    return [t for _, t in scored[:limit]]
