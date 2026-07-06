"""Shared fixtures.

- tmp_root (autouse): tmp_path-backed data root injected via paths.set_root()
  so tests never touch ~/ScreenKnowledge.
- db: migrated Database on tmp_root.
- cfg: Config built from defaults.
"""

from __future__ import annotations

import pytest

from screen_knowledge import paths
from screen_knowledge.config import Config
from screen_knowledge.db import Database


@pytest.fixture(autouse=True)
def tmp_root(tmp_path):
    paths.set_root(tmp_path)
    yield tmp_path
    paths.set_root(None)


@pytest.fixture
def db(tmp_root):
    paths.ensure_layout()
    d = Database(paths.db_file())
    d.migrate()
    yield d
    d.close()


@pytest.fixture
def cfg() -> Config:
    return Config()
