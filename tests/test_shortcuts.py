from quill.shortcuts import build_table, expand_shortcut, find_completed_shortcut


def test_find_completed_shortcut_with_args() -> None:
    match = find_completed_shortcut("before {table:2,3}")
    assert match is not None
    assert match.group(1) == "table"
    assert match.group(2) == "2,3"


def test_find_completed_shortcut_without_args() -> None:
    match = find_completed_shortcut("before {sig}")
    assert match is not None
    assert match.group(1) == "sig"
    assert match.group(2) is None


def test_find_completed_shortcut_requires_it_to_end_at_cursor() -> None:
    assert find_completed_shortcut("{table:2,3} and more text") is None


def test_find_completed_shortcut_ignores_unclosed_braces() -> None:
    assert find_completed_shortcut("typing {table:2,3") is None


def test_build_table_basic() -> None:
    table = build_table("2,3")
    lines = table.splitlines()
    assert lines[0] == "| Column 1 | Column 2 |"
    assert lines[1] == "| --- | --- |"
    assert len(lines) == 5  # header + divider + 3 rows
    assert all(line == "|  |  |" for line in lines[2:])


def test_build_table_defaults_to_one_row() -> None:
    table = build_table("3")
    assert len(table.splitlines()) == 3  # header + divider + 1 row


def test_build_table_zero_rows_is_header_only() -> None:
    table = build_table("2,0")
    assert len(table.splitlines()) == 2


def test_build_table_rejects_non_numeric_args() -> None:
    assert build_table("two,three") is None
    assert build_table("") is None
    assert build_table("0,1") is None  # zero columns doesn't make sense


def test_expand_shortcut_table() -> None:
    result = expand_shortcut(
        "table", "2,1", resolve_template=lambda _: None, custom_shortcuts={}
    )
    assert result == build_table("2,1")


def test_expand_shortcut_template_calls_resolver() -> None:
    def resolve(name: str) -> str | None:
        return "TEMPLATE BODY" if name == "Meeting Notes" else None

    result = expand_shortcut("template", "Meeting Notes", resolve_template=resolve, custom_shortcuts={})
    assert result == "TEMPLATE BODY"

    missing = expand_shortcut("template", "Nonexistent", resolve_template=resolve, custom_shortcuts={})
    assert missing is None


def test_expand_shortcut_custom() -> None:
    result = expand_shortcut(
        "sig", "", resolve_template=lambda _: None, custom_shortcuts={"sig": "Best,\nSomeone"}
    )
    assert result == "Best,\nSomeone"


def test_expand_shortcut_custom_does_not_match_with_args() -> None:
    # Custom shortcuts are the simple {name} form only, not {name:args}.
    result = expand_shortcut(
        "sig", "extra", resolve_template=lambda _: None, custom_shortcuts={"sig": "Best,\nSomeone"}
    )
    assert result is None


def test_expand_shortcut_unknown_name_returns_none() -> None:
    result = expand_shortcut("nonexistent", "", resolve_template=lambda _: None, custom_shortcuts={})
    assert result is None
