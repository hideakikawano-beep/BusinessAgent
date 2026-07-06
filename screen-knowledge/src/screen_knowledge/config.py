"""Config loading (pydantic over ~/ScreenKnowledge/config.yaml).

Contract (docs/10-phase1-capture.md):
- If config.yaml does not exist, create it from the packaged config.example.yaml
  content (falling back to model defaults) and load it.
- Section/key names mirror config.example.yaml exactly (docs/03 for semantics).
- `capture.interval_seconds == 0` means: continuous capture disabled, record
  only while a mark is active.

Defaults live on the models below so a partial config.yaml still validates.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import paths


class _Base(BaseModel):
    # tolerate unknown keys for forward-compat; validate the ones we know
    model_config = ConfigDict(extra="ignore")


class CaptureCfg(_Base):
    interval_seconds: int = 30
    marked_interval_seconds: int = 5
    on_window_change: bool = True
    window_change_debounce_s: int = 3
    idle_pause_after_s: int = 300
    store_long_edge_px: int = 2000


class DedupeCfg(_Base):
    phash_threshold: int = 8
    marked_phash_threshold: int = 4
    force_keyframe_s: int = 300


class ExcludeCfg(_Base):
    apps: list[str] = Field(
        default_factory=lambda: ["1Password", "KeePass", "Bitwarden", "LastPass"]
    )
    title_keywords: list[str] = Field(
        default_factory=lambda: [
            "パスワード",
            "password",
            "秘密",
            "給与",
            "マイナンバー",
            "banking",
            "口座",
        ]
    )


class MeetingCfg(_Base):
    apps: list[str] = Field(default_factory=lambda: ["zoom.us", "Zoom", "Microsoft Teams"])
    title_keywords: list[str] = Field(default_factory=lambda: ["Meet", "Webex"])
    capture_interval_s: int = 300


class SessionCfg(_Base):
    gap_s: int = 120
    interruption_tolerance_s: int = 60


class RetentionCfg(_Base):
    screenshot_days: int = 30
    frame_metadata_days: int = 180
    max_disk_gb: float = 10


class HotkeyCfg(_Base):
    enabled_windows: bool = True
    enabled_macos: bool = False
    combo: str = "<ctrl>+<alt>+m"


class ModelPrice(_Base):
    input: float
    output: float


class ApiCfg(_Base):
    key_source: Literal["keyring", "env", "config"] = "keyring"
    api_key: str = ""
    analysis_model: str = "claude-haiku-4-5"
    synthesis_model: str = "claude-sonnet-5"
    api_image_long_edge_px: int = 1024
    max_images_per_session: int = 12
    pricing: dict[str, ModelPrice] = Field(
        default_factory=lambda: {
            "claude-haiku-4-5": ModelPrice(input=1.0, output=5.0),
            "claude-sonnet-5": ModelPrice(input=3.0, output=15.0),
        }
    )
    batch_discount: float = 0.5


class AnalysisCfg(_Base):
    mode: Literal["nightly_batch", "realtime"] = "nightly_batch"
    nightly_at: str = "22:00"
    batch_poll_minutes: int = 15
    batch_fallback_after_h: int = 6
    min_session_ticks: int = 3


class BudgetCfg(_Base):
    monthly_usd: float = 25
    warn_ratio: float = 0.8
    daily_stored_frames_cap: int = 1500


class ViewerCfg(_Base):
    port: int = 8756
    allow_lan: bool = False


class NotionCfg(_Base):
    enabled: bool = False
    token: str = ""
    manuals_database_id: str = ""


class SlackCfg(_Base):
    enabled: bool = False
    webhook_url: str = ""
    post_at: str = "09:00"


class IntegrationsCfg(_Base):
    notion: NotionCfg = Field(default_factory=NotionCfg)
    slack: SlackCfg = Field(default_factory=SlackCfg)


class Config(_Base):
    """Typed view of config.yaml. See config.example.yaml for all keys."""

    language: str = "ja"
    capture: CaptureCfg = Field(default_factory=CaptureCfg)
    dedupe: DedupeCfg = Field(default_factory=DedupeCfg)
    exclude: ExcludeCfg = Field(default_factory=ExcludeCfg)
    meeting: MeetingCfg = Field(default_factory=MeetingCfg)
    session: SessionCfg = Field(default_factory=SessionCfg)
    retention: RetentionCfg = Field(default_factory=RetentionCfg)
    hotkey: HotkeyCfg = Field(default_factory=HotkeyCfg)
    api: ApiCfg = Field(default_factory=ApiCfg)
    analysis: AnalysisCfg = Field(default_factory=AnalysisCfg)
    budget: BudgetCfg = Field(default_factory=BudgetCfg)
    viewer: ViewerCfg = Field(default_factory=ViewerCfg)
    integrations: IntegrationsCfg = Field(default_factory=IntegrationsCfg)


def _example_path() -> Path:
    # src/screen_knowledge/config.py -> parents[2] == screen-knowledge/
    return Path(__file__).resolve().parents[2] / "config.example.yaml"


def _write_default_config(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    example = _example_path()
    if example.is_file():
        dest.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        # Fallback: dump model defaults (loses the example's comments).
        dest.write_text(
            yaml.safe_dump(Config().model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def load_config(path: Path | None = None) -> Config:
    """Load (and create-if-missing) the user config."""
    cfg_path = path or paths.config_file()
    if not cfg_path.exists():
        _write_default_config(cfg_path)
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return Config(**data)


def resolve_api_key(cfg: Config) -> str | None:
    """Resolve the Anthropic API key per api.key_source (keyring/env/config).

    Never log or echo the full key. Returns None if unset (P1 features must
    keep working without a key).
    """
    src = cfg.api.key_source
    key: str | None = None
    if src == "env":
        key = os.environ.get("ANTHROPIC_API_KEY")
    elif src == "config":
        key = cfg.api.api_key or None
    else:  # keyring
        try:
            import keyring

            key = keyring.get_password("screen-knowledge", "anthropic")
        except Exception:
            key = None
    return key or None
