"""Thin wrapper around the Anthropic SDK (Phase 2).

Responsibilities:
- API key resolution via config.resolve_api_key (keyring/env/config)
- retry policy: RateLimitError -> exponential backoff; 5xx -> retry (2);
  4xx -> raise immediately (caller marks session failed)
- every response's `usage` flows to BudgetGuard.record_usage
- image encoding helper: stored WebP -> resize to api.api_image_long_edge_px
  -> base64 (media_type image/webp)

Model IDs always come from config (api.analysis_model / api.synthesis_model);
never hardcode.
"""

from __future__ import annotations

from typing import Any


class AnthropicClient:
    def __init__(self, cfg, budget) -> None:  # config.Config, budget.BudgetGuard
        raise NotImplementedError("Phase 2")

    def parse_structured(
        self,
        *,
        model: str,
        system: str,
        user_content: list[dict[str, Any]],
        output_model: type,
        max_tokens: int,
        kind: str,
    ) -> Any:
        """messages.parse with retries + usage recording. Returns the validated
        pydantic instance."""
        raise NotImplementedError("Phase 2")

    def stream_text(
        self, *, model: str, system: str, user_text: str, max_tokens: int, kind: str
    ) -> str:
        """messages.stream + get_final_message for long text synthesis."""
        raise NotImplementedError("Phase 2")

    @property
    def batches(self) -> Any:
        """Underlying client.messages.batches (used by BatchRunner)."""
        raise NotImplementedError("Phase 2")


def encode_image_for_api(image_path, long_edge_px: int) -> dict[str, Any]:
    """Return an image content block (base64 WebP, resized)."""
    raise NotImplementedError("Phase 2")
