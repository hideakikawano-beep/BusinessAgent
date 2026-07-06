"""FastAPI viewer (Phase 4). Binds 127.0.0.1 unless viewer.allow_lan.

Routes (docs/13):
  GET /                    search box + recent daily logs + manuals
  GET /search?q=&type=     cross search with snippets
  GET /timeline/{date}     day's sessions + thumbnails (purged -> placeholder)
  GET /manuals             list (draft/published badges)
  GET /manuals/{slug}      md -> HTML
  GET /assets/{path}       images from vault/manuals/assets/ and shots/
                           — MUST resolve+verify under base dirs (no traversal)
  GET /status              heartbeat age, today's counts, monthly cost, errors

DB access: read-only connections per request (db.open_readonly). Templates:
Jinja2, no build step, no external CDN.
"""

from __future__ import annotations


def create_app(cfg, db_path):  # -> fastapi.FastAPI
    raise NotImplementedError("Phase 4")


def run_server(cfg) -> None:
    """uvicorn runner used by `sk serve` (separate process from the daemon)."""
    raise NotImplementedError("Phase 4")
