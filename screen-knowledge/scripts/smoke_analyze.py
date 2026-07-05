"""Real-API smoke test (Phase 2). MANUAL RUN ONLY — never in CI.

Creates one synthetic session (2 generated images: a fake CRM-ish window with
text) and runs the full analyze path against the real Anthropic API.
Asserts: SessionAnalysis validates, api_usage has real token counts,
total cost < $0.05. Prints the cost and the resulting analysis in Japanese.

Usage:
    uv run python scripts/smoke_analyze.py
"""

if __name__ == "__main__":
    raise SystemExit("Phase 2で実装されます (docs/11-phase2-analyze.md)")
