# Quill

## Summary

Quill is a terminal-only, command line note taking tool.

## Features

- Runs from a single command and opens an in-terminal editor making use of TUI for the interface for a more pleasant experience
- Stores note content in Markdown formatting
- Allows full create/read/update/delete of notes (confirming before delete)
- Allows for searching notes (including text search, date/time searches - exact and range, and fuzzy text searching if possible)
- Makes use of a sidebar for listing notes and allowing keyboard-driven browsing
- Automatically adds a date/time stamps to the note in frontmatter (created, last update)
- Notes can be stored in any directory but have in `~/.quill` by default
- Editor provides Markdown rendering as much as possible in the terminal
- Makes use of extended Markdown like GitHub offers
- Allows for subdirectories for organiziang notes
- Allows for cross-referencing notes using linking (example format: `[[<other not name]]` using a typical wiki style). If possible, allow for auto-complete or dynamic searching as the user types in the tag.
- Should allow for a quick add of a single note using an additional option on the command line
- Provides optional interface into an AI provider and includes tools that can be provided to that interface for working with notes
- Supports "to do" note formatting with checklists
- Supports "pinning" of notes that appear at the top of the sidebar in a "Pinned" section

## Technology

- Python

## Future plans

- Integration with external services such as GitHub (ex: being able to use the wiki-style linking to link to a GitHub PR and have it open the PR information pulled from GH when selected)