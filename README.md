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
| `a`       | Toggle AI assistant panel                 |
| `q`       | Quit                                      |

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

## AI assistant

When the `anthropic` extra is installed and `ANTHROPIC_API_KEY` is set,
pressing `a` opens a chat panel backed by Claude, with tools for searching,
reading, creating, and updating notes on your behalf. It's entirely optional
— everything else in Quill works without it.
