"""Immediate (non-batch) session analysis (Phase 2).

Path: keyframes (sampler, exclusion re-checked) -> image blocks + title
sequence -> parse_structured(SessionAnalysis, model=api.analysis_model,
max_tokens=4096) -> session_analyses row (+ image_ref -> frame_id mapping)
-> session status 'analyzed' (4xx/validation -> 'failed' + fail_reason).
Used for marked sessions (on close), realtime mode, and batch fallback.
"""

from __future__ import annotations

from .schemas import SessionAnalysis


class Analyzer:
    def __init__(self, cfg, db, client) -> None:  # AnthropicClient
        raise NotImplementedError("Phase 2")

    def analyze_session(self, session_id: int) -> SessionAnalysis:
        raise NotImplementedError("Phase 2")
