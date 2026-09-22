"""Command-line entry point for Quill."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from . import __version__
from .config import RC_PATH, load_config, load_settings, save_settings, set_setting
from .storage import NoteStore


def _derive_title_body(text: str) -> tuple[str, str]:
    text = text.strip()
    first_line, _, rest = text.partition("\n")
    if not rest and len(first_line) <= 60:
        return first_line, ""
    title = first_line[:60] if first_line else "Quick note"
    return title, text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quill", description="A terminal-only, TUI note taking tool.")
    parser.add_argument("--dir", metavar="PATH", help="Notes directory (defaults to $QUILL_NOTES_DIR or ~/.quill)")
    parser.add_argument("--version", action="version", version=f"quill {__version__}")
    parser.add_argument("-a", "--add", metavar="TEXT", help="Quickly add a note without opening the TUI")
    parser.add_argument("--title", help="Note title (used with -a/--add or 'add')")
    parser.add_argument("--folder", default="", help="Folder for the new note (used with -a/--add or 'add')")
    parser.add_argument("--pin", action="store_true", help="Pin the newly created note")

    subparsers = parser.add_subparsers(dest="command")
    add_parser = subparsers.add_parser("add", help="Quickly add a note without opening the TUI")
    add_parser.add_argument("text", nargs="+", help="Note text (becomes the title, or title+body if long)")
    add_parser.add_argument("-b", "--body", default="", help="Explicit body text (overrides auto-split)")
    add_parser.add_argument("--title", help="Note title")
    add_parser.add_argument("--folder", default="", help="Folder for the new note")
    add_parser.add_argument("--pin", action="store_true", help="Pin the newly created note")

    config_parser = subparsers.add_parser("config", help="View or change Quill settings (~/.quillrc)")
    config_sub = config_parser.add_subparsers(dest="config_action", required=True)

    config_sub.add_parser("show", help="Print the current settings")

    set_parser = config_sub.add_parser("set", help="Set a setting, e.g. 'quill config set notes_dir ~/notes'")
    set_parser.add_argument(
        "key",
        help=(
            "notes_dir, save_mode (autosave|manual), autosave_interval, "
            "history_enabled, max_revisions, "
            "ai.provider, ai.model, ai.api_key_env, ai.api_key, or ai.enabled"
        ),
    )
    set_parser.add_argument("value")

    config_sub.add_parser("edit", help="Open ~/.quillrc in $EDITOR")

    return parser


def _quick_add(store: NoteStore, text: str, title: str | None, folder: str, pinned: bool, body: str = "") -> None:
    if title:
        note = store.create(title=title, body=body or text, folder=folder, pinned=pinned)
    else:
        derived_title, derived_body = _derive_title_body(text)
        note = store.create(title=derived_title, body=body or derived_body, folder=folder, pinned=pinned)
    print(f"Created note: {note.rel_path}")


def _run_config_command(args: argparse.Namespace) -> int:
    if args.config_action == "show":
        cfg = load_settings()
        print(f"Settings file: {RC_PATH}{'' if RC_PATH.exists() else ' (not yet created; showing defaults)'}")
        print(f"notes_dir: {cfg.notes_dir}")
        print(f"save_mode: {cfg.save_mode}")
        print(f"autosave_interval: {cfg.autosave_interval}")
        print(f"history_enabled: {cfg.history_enabled}")
        print(f"max_revisions: {cfg.max_revisions}")
        print(f"ai.provider: {cfg.ai.provider}")
        print(f"ai.model: {cfg.ai.model}")
        print(f"ai.api_key_env: {cfg.ai.api_key_env}")
        print(f"ai.api_key: {'(set)' if cfg.ai.api_key else '(unset)'}")
        print(f"ai.enabled: {cfg.ai.enabled}")
        return 0
    if args.config_action == "set":
        try:
            set_setting(args.key, args.value)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Set {args.key} = {args.value}")
        return 0
    if args.config_action == "edit":
        if not RC_PATH.exists():
            save_settings(load_settings())
        editor = os.environ.get("EDITOR", "vi")
        subprocess.run([editor, str(RC_PATH)])
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        return _run_config_command(args)

    config = load_config(args.dir)
    store = NoteStore(config.notes_dir)

    if args.command == "add":
        text = " ".join(args.text)
        _quick_add(store, text, args.title, args.folder, args.pin, body=args.body)
        return 0

    if args.add:
        _quick_add(store, args.add, args.title, args.folder, args.pin)
        return 0

    from .app import run_app

    run_app(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
