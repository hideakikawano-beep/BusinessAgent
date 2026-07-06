"""Prompt templates (Phase 2/3).

Rules (docs/11):
- system prompts are FIXED strings (no timestamps/IDs interpolated) — cache
  friendly and diff-able. Session-specific data goes in the user turn.
- output language: Japanese. Step image references use the 画像N convention
  matching Step.image_ref.
- At ~1-2K tokens these prompts are below the cacheable minimum; do not add
  cache_control.

Templates to define here:
  ANALYSIS_SYSTEM   — session analysis instruction (SessionAnalysis)
  MATCHER_SYSTEM    — manual matching instruction (MatchResult, Phase 3)
  MANUAL_SYSTEM     — ManualDoc synthesis instruction (Phase 3)
  DAILY_LOG_SYSTEM  — daily log synthesis instruction (Phase 2)

User-turn builders:
  build_analysis_user(session_meta, title_sequence, n_images) -> str
  build_daily_log_user(analyses) -> str
"""

ANALYSIS_SYSTEM: str = ""  # Phase 2: 実装時に確定（固定文字列・日本語出力指示）
DAILY_LOG_SYSTEM: str = ""  # Phase 2
MATCHER_SYSTEM: str = ""  # Phase 3
MANUAL_SYSTEM: str = ""  # Phase 3
