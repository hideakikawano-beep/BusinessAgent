"""Structured-output schemas (frozen contract — docs/02).

API constraints (docs/11 落とし穴): additionalProperties must be false,
no numeric min/max or minLength (use Literal + descriptions), no recursion.
The SDK derives the JSON schema from these Pydantic models
(`client.messages.parse(..., output_format=SessionAnalysis)`); the Batch path
sends the same schema via output_config={"format": {"type": "json_schema", ...}}
and validates results with `SessionAnalysis.model_validate_json`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(description="このステップで行っていた操作（日本語・簡潔に）")
    image_ref: int | None = Field(
        default=None,
        description="根拠となる送信画像の番号（1始まり）。該当画像がなければnull",
    )


class SessionAnalysis(BaseModel):
    """Per-session analysis result stored in session_analyses (docs/03)."""

    model_config = ConfigDict(extra="forbid")

    task_label: str = Field(description="作業の短いラベル（日本語、例: HubSpotで商談ステージ更新）")
    task_category: Literal[
        "crm", "email", "docs", "research", "meeting", "spreadsheet", "presentation", "other"
    ]
    summary: str = Field(description="作業内容の要約（日本語2-4文）")
    steps: list[Step]
    apps: list[str] = Field(description="使用していたアプリ名")
    worth_documenting: bool = Field(
        description="定型的な操作手順としてマニュアル化する価値があるか"
    )
    worth_documenting_reason: str
    notable_facts: list[str] = Field(
        description="ナレッジとして残す価値のある気づき・学び（なければ空配列）"
    )
    confidence: Literal["high", "medium", "low"]


class MatchResult(BaseModel):
    """ManualMatcher output (Phase 3)."""

    model_config = ConfigDict(extra="forbid")

    match_manual_id: int | None = Field(
        description="内容が同一手順を指す既存マニュアルのID。確信が持てなければnull"
    )
    confidence: Literal["high", "medium", "low"]
