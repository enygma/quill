from quill.widgets.modals import _shortcut_rows


def test_shortcut_rows_includes_builtins_with_no_custom() -> None:
    rows = _shortcut_rows({})
    keys = [key for key, _ in rows]
    assert "{table:cols,rows}" in keys
    assert "{template:Note Title}" in keys
    assert len(rows) == 2


def test_shortcut_rows_includes_custom_shortcuts_sorted() -> None:
    rows = _shortcut_rows({"zed": "last", "alpha": "first"})
    custom_keys = [key for key, _ in rows[2:]]
    assert custom_keys == ["{alpha}", "{zed}"]


def test_shortcut_rows_shows_a_preview_of_the_replacement() -> None:
    rows = _shortcut_rows({"sig": "Best,\nSomeone"})
    _, desc = rows[-1]
    assert desc == "-> 'Best,\\nSomeone'"  # newline escaped for a single-line preview


def test_shortcut_rows_truncates_long_replacements() -> None:
    long_text = "x" * 100
    rows = _shortcut_rows({"long": long_text})
    _, desc = rows[-1]
    assert "..." in desc
    assert len(desc) < len(long_text)
