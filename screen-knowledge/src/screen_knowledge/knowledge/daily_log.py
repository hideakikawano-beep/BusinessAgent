"""Daily work log generation (Phase 2).

Input: the day's analyzed session_analyses (text only — no images sent).
Output: vault/daily/YYYY-MM-DD.md per the format in docs/03-data-model.md
(サマリー / タイムライン / 気づき・ナレッジ候補 + auto-generated footer),
model=api.synthesis_model via AnthropicClient.stream_text (max_tokens=8192).
Regeneration overwrites the file and updates daily_logs.updated_at.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path


def generate_daily_log(db, date: dt.date, client, cfg) -> Path:
    raise NotImplementedError("Phase 2")
