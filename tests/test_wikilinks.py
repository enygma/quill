from quill.wikilinks import (
    find_link_targets,
    find_links,
    find_open_link,
    is_url,
    is_wiki_href,
    render_for_preview,
    suggest_titles,
)


def test_find_links() -> None:
    text = "See [[Note One]] and also [[Note Two|custom label]]."
    assert find_links(text) == ["Note One", "Note Two|custom label"]


def test_find_link_targets_parses_aliases_and_dedupes() -> None:
    text = "See [[Note One]] and [[Note Two|custom label]], and again [[Note One]]."
    assert find_link_targets(text) == [("Note One", "Note One"), ("Note Two", "custom label")]


def test_find_link_targets_empty() -> None:
    assert find_link_targets("no links here") == []


def test_find_link_targets_includes_regular_markdown_links() -> None:
    text = "Check the [markdown link](Other Note) for details."
    assert find_link_targets(text) == [("Other Note", "markdown link")]


def test_find_link_targets_markdown_link_target_may_contain_spaces() -> None:
    # Unlike strict CommonMark, a bare (unescaped) space in the target is
    # allowed here, since it's routinely a note title.
    text = "[label](Some Note Title)"
    assert find_link_targets(text) == [("Some Note Title", "label")]


def test_find_link_targets_excludes_images() -> None:
    text = "![alt text](image.png)"
    assert find_link_targets(text) == []


def test_find_link_targets_combines_wiki_and_markdown_links_in_order() -> None:
    text = "See [[Wiki One]] then [md link](Markdown Target)."
    assert find_link_targets(text) == [("Wiki One", "Wiki One"), ("Markdown Target", "md link")]


def test_is_url() -> None:
    assert is_url("https://example.com/page") is True
    assert is_url("http://example.com") is True
    assert is_url("Other Note") is False
    assert is_url("wiki:Other Note") is False


def test_find_open_link_detects_unclosed_brackets() -> None:
    assert find_open_link("See [[Proj") == "Proj"
    assert find_open_link("See [[Project]] and [[Other") == "Other"
    assert find_open_link("No link here") is None
    assert find_open_link("[[Closed]]") is None


def test_render_for_preview_converts_to_markdown_links() -> None:
    rendered, broken = render_for_preview("See [[Other Note]] for details.")
    assert rendered == "See [Other Note](wiki:Other%20Note) for details."
    assert broken == []


def test_render_for_preview_supports_alias() -> None:
    rendered, broken = render_for_preview("[[Other Note|click here]]")
    assert rendered == "[click here](wiki:Other%20Note)"
    assert broken == []


def test_render_for_preview_encodes_spaces_and_hashes() -> None:
    # Regression test: a Markdown link destination with an unescaped space
    # isn't valid CommonMark, so a title like "test note #1" used to render
    # as literal, unclickable text -- "[test note #1](wiki:test note #1)" --
    # instead of an actual link. The target must be percent-encoded to stay
    # a single valid "word" in the link destination.
    rendered, _broken = render_for_preview("See [[test note #1]] for details.")
    assert rendered == "See [test note #1](wiki:test%20note%20%231) for details."
    assert " " not in rendered.split("(wiki:", 1)[1].split(")")[0]


def test_render_for_preview_roundtrips_through_is_wiki_href() -> None:
    # What Textual's Markdown.LinkClicked hands back (it unquotes hrefs
    # itself) should recover the original title exactly.
    from urllib.parse import unquote

    rendered, _broken = render_for_preview("[[test note #1]]")
    href = rendered.split("(", 1)[1].rstrip(")")
    assert is_wiki_href(unquote(href)) == "test note #1"


def test_render_for_preview_flags_broken_links_as_non_clickable() -> None:
    def resolve(target: str) -> bool:
        return target == "Real Note"

    rendered, broken = render_for_preview("See [[Real Note]] and [[Ghost Note]].", resolve=resolve)
    assert "[Real Note](wiki:Real%20Note)" in rendered
    assert "`⚠ Ghost Note`" in rendered
    assert "wiki:Ghost" not in rendered  # not rendered as a clickable link
    assert broken == ["Ghost Note"]


def test_render_for_preview_dedupes_repeated_broken_links() -> None:
    def resolve(_target: str) -> bool:
        return False

    _rendered, broken = render_for_preview("[[Ghost]] and again [[Ghost]].", resolve=resolve)
    assert broken == ["Ghost"]


def test_is_wiki_href() -> None:
    assert is_wiki_href("wiki:Other Note") == "Other Note"
    assert is_wiki_href("https://example.com") is None


def test_suggest_titles_ranks_by_relevance() -> None:
    titles = ["Grocery List", "Trip Plan", "Groceries for Party"]
    suggestions = suggest_titles("Groc", titles)
    assert set(suggestions) == {"Grocery List", "Groceries for Party"}
    assert "Trip Plan" not in suggestions


def test_suggest_titles_narrows_by_substring() -> None:
    # "test n" is a substring of "test note 1" but not "test 1", so typing
    # it should filter the list down rather than just re-rank it.
    titles = ["test 1", "test note 1"]
    assert suggest_titles("test n", titles) == ["test note 1"]


def test_suggest_titles_prefix_matches_rank_first() -> None:
    titles = ["Notes App", "My daily notes"]
    assert suggest_titles("notes", titles) == ["Notes App", "My daily notes"]


def test_suggest_titles_falls_back_to_fuzzy_for_typos() -> None:
    # No title contains "grocry" as a substring, so it should fall back to
    # fuzzy matching rather than returning nothing.
    titles = ["Grocery List", "Trip Plan"]
    assert suggest_titles("grocry", titles) == ["Grocery List"]


def test_suggest_titles_empty_partial_returns_sorted() -> None:
    titles = ["B", "A", "C"]
    assert suggest_titles("", titles) == ["A", "B", "C"]
