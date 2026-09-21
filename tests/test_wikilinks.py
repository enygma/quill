from quill.wikilinks import find_links, find_open_link, is_wiki_href, render_for_preview, suggest_titles


def test_find_links() -> None:
    text = "See [[Note One]] and also [[Note Two|custom label]]."
    assert find_links(text) == ["Note One", "Note Two|custom label"]


def test_find_open_link_detects_unclosed_brackets() -> None:
    assert find_open_link("See [[Proj") == "Proj"
    assert find_open_link("See [[Project]] and [[Other") == "Other"
    assert find_open_link("No link here") is None
    assert find_open_link("[[Closed]]") is None


def test_render_for_preview_converts_to_markdown_links() -> None:
    rendered = render_for_preview("See [[Other Note]] for details.")
    assert rendered == "See [Other Note](wiki:Other Note) for details."


def test_render_for_preview_supports_alias() -> None:
    rendered = render_for_preview("[[Other Note|click here]]")
    assert rendered == "[click here](wiki:Other Note)"


def test_is_wiki_href() -> None:
    assert is_wiki_href("wiki:Other Note") == "Other Note"
    assert is_wiki_href("https://example.com") is None


def test_suggest_titles_ranks_by_relevance() -> None:
    titles = ["Grocery List", "Trip Plan", "Groceries for Party"]
    suggestions = suggest_titles("Groc", titles)
    assert suggestions[0] in {"Grocery List", "Groceries for Party"}
    assert "Trip Plan" not in suggestions or len(suggestions) == len(titles)


def test_suggest_titles_empty_partial_returns_sorted() -> None:
    titles = ["B", "A", "C"]
    assert suggest_titles("", titles) == ["A", "B", "C"]
