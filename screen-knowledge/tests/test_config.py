from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from screen_knowledge import paths
from screen_knowledge.config import Config, load_config, resolve_api_key


def test_creates_config_when_missing():
    assert not paths.config_file().exists()
    cfg = load_config()
    assert paths.config_file().exists()
    assert cfg.capture.interval_seconds == 30
    assert cfg.budget.monthly_usd == 25


def test_partial_config_keeps_defaults():
    paths.config_file().parent.mkdir(parents=True, exist_ok=True)
    paths.config_file().write_text(
        yaml.safe_dump({"capture": {"interval_seconds": 10}}), encoding="utf-8"
    )
    cfg = load_config()
    assert cfg.capture.interval_seconds == 10
    assert cfg.capture.marked_interval_seconds == 5  # default preserved
    assert cfg.dedupe.phash_threshold == 8


def test_interval_zero_allowed():
    cfg = Config(capture={"interval_seconds": 0})
    assert cfg.capture.interval_seconds == 0


def test_invalid_value_rejected():
    with pytest.raises(ValidationError):
        Config(capture={"interval_seconds": "not-a-number"})


def test_resolve_api_key_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    cfg = Config(api={"key_source": "env"})
    assert resolve_api_key(cfg) == "sk-test-123"


def test_resolve_api_key_config():
    cfg = Config(api={"key_source": "config", "api_key": "sk-cfg"})
    assert resolve_api_key(cfg) == "sk-cfg"


def test_resolve_api_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = Config(api={"key_source": "env"})
    assert resolve_api_key(cfg) is None
