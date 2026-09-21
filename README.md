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
| `n`       | New note (in whichever folder is highlighted in the sidebar) |
| `f`       | New folder (created one level under the current note's folder) |
| `e`       | Edit selected note                        |
| `ctrl+s`  | Save (while editing)                      |
| `escape`  | Cancel edit / close dialog                |
| `d`       | Delete selected note (asks to confirm)    |
| `p`       | Pin/unpin selected note                   |
| `m`       | Move selected note to a different folder  |
| `r`       | Rename the selected note, or a highlighted folder |
| `g`       | Go to a link in the current note (wiki or markdown; picker if several) |
| `/`       | Search (text, fuzzy, or date)             |
| `ctrl+t`  | Toggle checkbox on current editor line    |
| `a`       | Toggle AI assistant panel (only shown if enabled in settings) |
| `s`       | Settings (notes directory, saving, AI connection) |
| `b`       | Jump focus back to the sidebar            |
| `?`       | Show the keyboard shortcuts help popup    |
| `q`       | Quit                                      |

Press `?` any time in the app for a full, categorized list of shortcuts.
Up/Down navigate the sidebar (and any results list); Enter opens what's
highlighted. Any folder field (new note, move) suggests existing folders as
you type, narrowed the same way wiki-link autocomplete is.

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

Notes can live in subdirectories of the notes root for organization — create
one with `f` (it's added one level under whichever note is currently open, or
at the top level if none is), or just give `n`/`quill add` a `folder` and it's
created automatically. Empty folders show up in the sidebar too, ready for
notes to be added into them. Move a note to a different folder with `m`, or
rename a note or a folder with `r` (highlight the folder in the sidebar
first). Notes can cross-reference each other with
wiki-style links: `[[Other Note]]` or
`[[Other Note|custom label]]`. While typing `[[` in the editor, Quill shows
live autocomplete suggestions drawn from existing note titles, narrowed as
you keep typing. A regular Markdown link works too, e.g. `[label](Other Note)`.
In preview mode, click a link to follow it, or press `g` to jump to it (or
pick from a list, if there's more than one) without a mouse — a link to a
URL opens in your browser instead of looking for a note.

If a `[[wiki link]]` points at a note that's since been renamed, moved, or
deleted, the preview flags it: a warning banner appears across the top of
the note, and the broken reference itself is shown in red instead of as a
clickable link (CommonMark has no notion of per-link color, so it can't
keep the normal link appearance — just an unmistakable one).

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
