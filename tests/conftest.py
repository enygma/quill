"""Test-wide safety net: never let a test touch the real ~/.quillrc."""

from pathlib import Path

import pytest

import quill.config as config_module


@pytest.fixture(autouse=True)
def isolated_rc_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module, "RC_PATH", tmp_path / ".quillrc-test")
