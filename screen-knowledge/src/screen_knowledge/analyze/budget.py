"""Budget guard — hard monthly stop (Phase 2).

Semantics (docs/11):
- allow(): month-to-date cost (api_usage.cost_usd sum, local-time month) plus
  the estimate must stay under budget.monthly_usd. When over: analysis calls
  are refused, sessions stay 'queued', CAPTURE CONTINUES, tray shows 上限到達.
- record_usage(): cost computed at record time from config api.pricing
  (input/output USD per 1M tokens) x batch_discount when is_batch.
- warn threshold budget.warn_ratio (0.8) -> tray warning text.
"""

from __future__ import annotations

from typing import Any


class BudgetGuard:
    def __init__(self, cfg, db) -> None:
        raise NotImplementedError("Phase 2")

    def allow(self, kind: str, est_usd: float) -> bool:
        raise NotImplementedError("Phase 2")

    def record_usage(
        self,
        *,
        model: str,
        usage: Any,          # anthropic Usage object (input/output/cache tokens)
        is_batch: bool,
        kind: str,
        request_id: str | None = None,
        batch_id: str | None = None,
    ) -> None:
        raise NotImplementedError("Phase 2")

    def month_to_date_usd(self) -> float:
        raise NotImplementedError("Phase 2")

    def status_text(self) -> str:
        """Japanese one-liner for tray/status (e.g. '今月 $3.20 / $25')."""
        raise NotImplementedError("Phase 2")
