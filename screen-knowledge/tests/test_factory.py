from __future__ import annotations

import sys

import pytest

from screen_knowledge.capture.adapters.factory import make_adapters
from screen_knowledge.config import Config


@pytest.mark.skipif(
    sys.platform in ("win32", "darwin"), reason="unsupported-OS path only"
)
def test_unsupported_os_raises():
    with pytest.raises(RuntimeError):
        make_adapters(Config())
