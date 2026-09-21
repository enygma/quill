from quill.checklist import render_checklists_for_preview


def test_checked_item_becomes_green_checkmark() -> None:
    assert render_checklists_for_preview("- [x] Walk the dog") == "- ✅ Walk the dog"


def test_unchecked_item_becomes_empty_box() -> None:
    assert render_checklists_for_preview("- [ ] Buy milk") == "- ☐ Buy milk"


def test_uppercase_x_counts_as_checked() -> None:
    assert render_checklists_for_preview("- [X] Done") == "- ✅ Done"


def test_preserves_indentation_for_nested_items() -> None:
    text = "- [ ] Parent\n  - [x] Child"
    assert render_checklists_for_preview(text) == "- ☐ Parent\n  - ✅ Child"


def test_leaves_non_checklist_list_items_alone() -> None:
    text = "- A plain bullet\n- Another one"
    assert render_checklists_for_preview(text) == text


def test_leaves_unrelated_text_alone() -> None:
    text = "Just a paragraph mentioning [x] in passing, not a list item."
    assert render_checklists_for_preview(text) == text
