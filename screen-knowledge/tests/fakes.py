"""Test doubles (implemented per phase; contracts fixed here).

FakeClock (P1)      — manual now()/sleep(); drives tick cadence & purge tests
FakeAdapters (P1)   — scripted WindowInfo / idle-seconds sequences; synthetic
                      PIL images with drawn text so pHash distances are
                      controllable; implements all base.py Protocols including
                      a no-op TrayAdapter
FakeAnthropicClient (P2) — .messages.parse / .messages.create /
                      .messages.batches.{create,retrieve,results} with canned
                      pydantic-valid payloads, usage objects, and fault
                      injection (rate-limit, 500, schema-violating JSON,
                      batch expired). Scenario scripting: a list of queued
                      responses consumed in order (multi-call flows in P3).
No fake may perform network or GUI operations.
"""
