from datetime import datetime
from pathlib import Path

from quill.models import Note
from quill.search import date_search, fuzzy_search, parse_date_query, text_search


def make_note(rel_path: str, title: str, body: str = "", **kwargs) -> Note:
    return Note(path=Path(f"{rel_path}.md"), rel_path=rel_path, title=title, body=body, **kwargs)


def test_text_search_matches_title_and_body() -> None:
    notes = [
        make_note("a", "Grocery List", "milk, eggs"),
        make_note("b", "Trip Plan", "flights and hotels"),
    ]
    results = text_search(notes, "milk")
    assert len(results) == 1
    assert results[0].note.rel_path == "a"


def test_text_search_ranks_title_matches_higher() -> None:
    notes = [
        make_note("a", "Something Else", "mentions grocery in passing"),
        make_note("b", "Grocery List", "milk, eggs"),
    ]
    results = text_search(notes, "grocery")
    assert results[0].note.rel_path == "b"


def test_fuzzy_search_tolerates_typos() -> None:
    notes = [make_note("a", "Grocery List"), make_note("b", "Trip Plan")]
    results = fuzzy_search(notes, "Grocry List")
    assert results
    assert results[0].note.rel_path == "a"


def test_date_search_exact_day() -> None:
    notes = [
        make_note("a", "A", updated="2026-09-21T10:00:00"),
        make_note("b", "B", updated="2026-09-20T10:00:00"),
    ]
    results = date_search(notes, on=datetime(2026, 9, 21))
    assert len(results) == 1
    assert results[0].note.rel_path == "a"


def test_date_search_range() -> None:
    notes = [
        make_note("a", "A", updated="2026-09-21T10:00:00"),
        make_note("b", "B", updated="2026-09-10T10:00:00"),
        make_note("c", "C", updated="2026-09-25T10:00:00"),
    ]
    results = date_search(notes, since=datetime(2026, 9, 15), until=datetime(2026, 9, 22))
    rel_paths = {r.note.rel_path for r in results}
    assert rel_paths == {"a"}


def test_parse_date_query() -> None:
    assert parse_date_query("2026-09-21") == datetime(2026, 9, 21)
    assert parse_date_query("2026-09-21 10:30") == datetime(2026, 9, 21, 10, 30)
    assert parse_date_query("garbage") is None
