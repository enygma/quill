"""Wiki-style [[note]] link parsing and autocomplete support."""

from __future__ import annotations

import re
from urllib.parse import quote

from rapidfuzz import fuzz

WIKILINK_RE = re.compile(r"\[\[([^\[\]]*)\]\]")

# [[Target]] or [[Target|Custom Label]]
FULL_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|([^\[\]]+))?\]\]")

# Standard Markdown [text](target), e.g. a link pasted or typed directly
# rather than as a [[wiki link]]. The negative lookbehind excludes image
# syntax ![alt](src). Targets can't themselves contain literal parentheses,
# but -- unlike strict CommonMark -- spaces are allowed unescaped, since a
# target here is routinely a note title (e.g. "[label](Other Note)").
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\[\]]+)\]\(([^()]+)\)")

WIKI_SCHEME = "wiki:"

# Matches an *unclosed* [[ that the cursor is currently typing inside,
# e.g. "See [[proj" -> capture group "proj"
OPEN_WIKILINK_RE = re.compile(r"\[\[([^\[\]]*)$")


def find_links(text: str) -> list[str]:
    """Return all wiki-link targets referenced in text."""
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text) if m.group(1).strip()]


def find_link_targets(text: str) -> list[tuple[str, str]]:
    """Return (target, label) pairs for every [[wiki link]] AND standard
    Markdown [text](target) link in text, in first-seen order, deduplicated
    by target. Used for the 'g' keyboard shortcut and the link picker, so
    both link styles are navigable the same way."""
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for pattern, groups in ((FULL_WIKILINK_RE, (1, 2)), (MARKDOWN_LINK_RE, (2, 1))):
        target_group, label_group = groups
        for match in pattern.finditer(text):
            target = match.group(target_group).strip()
            label = (match.group(label_group) or target).strip()
            if target and target not in seen:
                seen.add(target)
                results.append((target, label))
    return results


def is_url(target: str) -> bool:
    return target.startswith(("http://", "https://"))


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

    Note titles routinely contain spaces (and sometimes '#'), but a Markdown
    link destination with an unescaped space isn't valid CommonMark -- the
    parser just falls back to literal text instead of a link. The target is
    percent-encoded here to keep it a single valid "word"; Textual's
    `Markdown.LinkClicked` already unquotes the href automatically, so
    `is_wiki_href` gets the original text back with no extra decoding.
    """

    def _sub(match: re.Match) -> str:
        target = match.group(1).strip()
        label = (match.group(2) or target).strip()
        return f"[{label}]({WIKI_SCHEME}{quote(target)})"

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
