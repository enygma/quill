# Quill

A terminal-only, keyboard-driven note taking tool. Notes are stored as plain
Markdown files with YAML frontmatter, browsed and edited through a TUI built
with [Textual](https://textual.textualize.io/).

## Install

```bash
uv sync
uv run quill
```

Or with pip, in a virtualenv:

```bash
pip install -e .
quill
```

For the optional AI assistant:

```bash
pip install -e ".[ai]"
export ANTHROPIC_API_KEY=sk-...
```

## Usage

```bash
quill                       # open the TUI (defaults to ~/.quill)
quill --dir ./notes         # use a different notes directory
quill add "Buy milk"        # quick-add a note without opening the TUI
quill add "Title" -b "Body text" --folder projects
```

The notes directory can also be set via the `QUILL_NOTES_DIR` environment
variable.

## Keybindings

| Key       | Action                                   |
|-----------|-------------------------------------------|
| `n`       | New note                                  |
| `e`       | Edit selected note                        |
| `ctrl+s`  | Save (while editing)                      |
| `escape`  | Cancel edit / close dialog                |
| `d`       | Delete selected note (asks to confirm)    |
| `p`       | Pin/unpin selected note                   |
| `/`       | Search (text, fuzzy, or date)             |
| `ctrl+t`  | Toggle checkbox on current editor line    |
| `a`       | Toggle AI assistant panel (only shown if enabled in settings) |
| `s`       | Settings (notes directory, saving, AI connection) |
| `?`       | Show the keyboard shortcuts help popup    |
| `q`       | Quit                                      |

Press `?` any time in the app for a full, categorized list of shortcuts.
Up/Down navigate the sidebar (and any results list); Enter opens what's
highlighted.

If you quit (`q` or `ctrl+q`) while an edit hasn't been saved yet, Quill
asks for confirmation first rather than silently discarding it.

## Notes format

Each note is a `.md` file with frontmatter:

```markdown
---
title: Grocery List
created: 2026-09-21T10:00:00
updated: 2026-09-21T10:05:00
pinned: false
tags: []
---

- [ ] Milk
- [ ] Eggs
- [x] Coffee
```

Notes can live in subdirectories of the notes root for organization, and can
cross-reference each other with wiki-style links: `[[Other Note]]` or
`[[Other Note|custom label]]`. While typing `[[` in the editor, Quill shows
live autocomplete suggestions drawn from existing note titles.

## Saving

By default, Quill autosaves the note you're editing every 5 seconds (only
while it actually has unsaved changes). `ctrl+s` always saves immediately too,
in either mode, and also exits back to preview.

Switch to manual saving — nothing is written to disk until you press
`ctrl+s` — from the Settings screen (`s`) or the CLI:

```bash
quill config set save_mode manual      # or: autosave
quill config set autosave_interval 10  # seconds; only used in autosave mode
```

## AI assistant

When the `anthropic` extra is installed and `ANTHROPIC_API_KEY` is set,
pressing `a` opens a chat panel backed by Claude, with tools for searching,
reading, creating, and updating notes on your behalf. It's entirely optional
— everything else in Quill works without it.
