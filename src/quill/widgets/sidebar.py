"""Sidebar: a Pinned section plus a folder tree of notes, keyboard browsable."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ..models import Note


class NoteHighlighted(Message):
    """Cursor moved to a note in the sidebar (live preview should follow)."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        super().__init__()


class NoteChosen(Message):
    """User pressed Enter / double-clicked a note in the sidebar."""

    def __init__(self, rel_path: str) -> None:
        self.rel_path = rel_path
        super().__init__()


class Sidebar(Tree[str]):
    """Tree-based sidebar. Node `data` holds a note's rel_path, or None for
    folder / section header nodes."""

    def __init__(self) -> None:
        super().__init__("Quill", id="sidebar")
        self.show_root = False
        self.guide_depth = 2
        self._node_by_rel: dict[str, TreeNode[str]] = {}

    def refresh_notes(
        self,
        notes: list[Note],
        selected_rel: str | None = None,
        folders: list[str] | None = None,
    ) -> None:
        expanded_folders = self._expanded_folders()
        self.clear()
        self._node_by_rel.clear()

        pinned = sorted((n for n in notes if n.pinned), key=lambda n: n.title.lower())
        unpinned = sorted((n for n in notes if not n.pinned), key=lambda n: (n.folder, n.title.lower()))

        if pinned:
            pinned_node = self.root.add("📌 Pinned", expand=True)
            for note in pinned:
                leaf = pinned_node.add_leaf(f"📝 {note.title}", data=note.rel_path)
                self._node_by_rel.setdefault(note.rel_path, leaf)

        folder_nodes: dict[str, TreeNode[str]] = {"": self.root}

        def get_folder_node(folder: str) -> TreeNode[str]:
            if folder in folder_nodes:
                return folder_nodes[folder]
            parent_folder = "/".join(folder.split("/")[:-1])
            parent_node = get_folder_node(parent_folder)
            name = folder.split("/")[-1]
            node = parent_node.add(f"📁 {name}", expand=(folder in expanded_folders or not expanded_folders))
            folder_nodes[folder] = node
            return node

        for note in unpinned:
            parent_node = get_folder_node(note.folder)
            leaf = parent_node.add_leaf(f"📝 {note.title}", data=note.rel_path)
            self._node_by_rel.setdefault(note.rel_path, leaf)

        # Also materialize folders that don't (yet) contain any notes, e.g.
        # ones just created with 'f', so they're visible immediately.
        for folder in sorted(folders or []):
            get_folder_node(folder)

        if not notes:
            self.root.add_leaf("(no notes yet — press 'n' to create one)")

        if selected_rel and selected_rel in self._node_by_rel:
            node = self._node_by_rel[selected_rel]
            # Deliberately move_cursor() rather than select_node(): the latter
            # also posts a NodeSelected message, which would make every
            # refresh_sidebar() call re-trigger note-open handling (and could
            # clobber in-progress edit state) as an unintended side effect.
            self.move_cursor(node)

    def _expanded_folders(self) -> set[str]:
        # Best-effort: not persisted across full rebuild by name; kept simple.
        return set()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if event.node.data:
            self.post_message(NoteHighlighted(event.node.data))

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data:
            self.post_message(NoteChosen(event.node.data))
