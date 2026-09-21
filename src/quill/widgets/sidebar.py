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


# Folder nodes carry their folder path in `data` too (prefixed, so they're
# distinguishable from a note's rel_path), so the app can ask "what folder
# is currently highlighted" to default where a new note/folder goes, or
# where a note gets moved to.
_FOLDER_DATA_PREFIX = "\x00folder:"


def _folder_data(folder: str) -> str:
    return f"{_FOLDER_DATA_PREFIX}{folder}"


def _is_folder_data(data: str) -> bool:
    return data.startswith(_FOLDER_DATA_PREFIX)


def _folder_from_data(data: str) -> str:
    return data[len(_FOLDER_DATA_PREFIX):]


class Sidebar(Tree[str]):
    """Tree-based sidebar. Node `data` holds a note's rel_path, a folder's
    path (prefixed, see above), or is None for section headers."""

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

        # Always shown, even with nothing pinned yet, so it's a consistent
        # landmark at the top of the sidebar rather than appearing/
        # disappearing as notes get pinned and unpinned.
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
            node = parent_node.add(
                f"📁 {name}",
                data=_folder_data(folder),
                expand=(folder in expanded_folders or not expanded_folders),
            )
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
            #
            # Deferred via call_after_refresh(): TreeNode.line is a cached
            # value only recomputed during an actual render pass, not
            # synchronously as nodes are added above. Calling move_cursor()
            # immediately here would read stale line numbers left over from
            # the tree's previous structure (pointing at the wrong node) --
            # deferring until after a layout pass has happened avoids that.
            self.call_after_refresh(self.move_cursor, node)

    def _expanded_folders(self) -> set[str]:
        # Best-effort: not persisted across full rebuild by name; kept simple.
        return set()

    @staticmethod
    def note_rel_path_for(node: TreeNode[str] | None) -> str | None:
        """The note rel_path for this node, or None if it's a folder header,
        the pinned-section header, or empty."""
        if node is None or not node.data or _is_folder_data(node.data):
            return None
        return node.data

    @staticmethod
    def folder_for(node: TreeNode[str] | None) -> str | None:
        """The folder path for this node, or None if it's not a folder header."""
        if node is None or not node.data or not _is_folder_data(node.data):
            return None
        return _folder_from_data(node.data)

    def current_folder(self) -> str:
        """Best-effort folder context for whatever is currently highlighted
        (a note, or a folder itself) -- used to default where a new
        note/folder is created, or where a note gets moved to."""
        node = self.cursor_node
        if node is None or not node.data:
            return ""
        if _is_folder_data(node.data):
            return _folder_from_data(node.data)
        return "/".join(node.data.split("/")[:-1])  # note rel_path -> its folder

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        data = event.node.data
        if data and not _is_folder_data(data):
            self.post_message(NoteHighlighted(data))

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if data and not _is_folder_data(data):
            self.post_message(NoteChosen(data))
