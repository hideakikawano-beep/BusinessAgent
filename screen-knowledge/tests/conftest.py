"""Shared fixtures.

Phase 1 implements:
- tmp_root: tmp_path-backed data root injected via paths.set_root() so tests
  never touch ~/ScreenKnowledge (autouse)
- db: migrated Database on tmp_root
- cfg: Config built from config.example.yaml defaults with test overrides
"""
