"""ScreenKnowledge — PC作業の自動ナレッジ化ツール.

Package layout (see docs/02-architecture.md):
    config / paths / db   : foundations (Phase 1)
    capture/              : capture daemon, dedupe, storage, OS adapters (Phase 1)
    sessionize/           : frame -> session grouping, keyframe sampling (Phase 2)
    analyze/              : Claude API client, structured outputs, batch, budget (Phase 2)
    knowledge/            : manuals, matcher, daily log, vault writer (Phase 2/3)
    viewer/               : local search UI (Phase 4)
"""

__version__ = "0.1.0"
