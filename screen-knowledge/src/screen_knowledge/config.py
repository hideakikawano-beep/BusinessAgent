"""Config loading (pydantic-settings over ~/ScreenKnowledge/config.yaml).

Contract (docs/10-phase1-capture.md):
- If config.yaml does not exist, create it from the packaged config.example.yaml
  content and load the defaults.
- Section/key names mirror config.example.yaml exactly (single source of truth
  for defaults; docs/03-data-model.md for semantics).
- `capture.interval_seconds == 0` means: continuous capture disabled, record
  only while a mark is active.

Implementation note: define one pydantic model per YAML section (CaptureCfg,
DedupeCfg, ExcludeCfg, MeetingCfg, RetentionCfg, HotkeyCfg, ApiCfg,
AnalysisCfg, BudgetCfg, ViewerCfg, IntegrationsCfg) aggregated by `Config`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class Config:  # placeholder — Phase 1 replaces with a pydantic BaseModel tree
    """Typed view of config.yaml. See config.example.yaml for all keys."""

    def __init__(self, **data: Any) -> None:
        raise NotImplementedError("Phase 1")


def load_config(path: Path | None = None) -> Config:
    """Load (and create-if-missing) the user config."""
    raise NotImplementedError("Phase 1")


def resolve_api_key(cfg: Config) -> str | None:
    """Resolve the Anthropic API key per api.key_source (keyring/env/config).

    Never log or echo the full key. Returns None if unset (P1 features must
    keep working without a key).
    """
    raise NotImplementedError("Phase 1")
