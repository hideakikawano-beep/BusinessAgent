"""Test doubles (contracts fixed in docs/02). No network or GUI.

FakeClock            — manual now()/sleep(); drives cadence & purge tests
Fake*Adapter         — implement the base.py Protocols
make_image(seed)     — deterministic noise image; same seed => identical phash,
                       different seed => large phash distance (controls dedupe)
"""

from __future__ import annotations

import datetime as dt
import random

from PIL import Image

from screen_knowledge.capture.adapters.base import (
    Adapters,
    Capture,
    PermissionStatus,
    TrayMenuSpec,
    WindowInfo,
)


def make_image(seed: int, size: tuple[int, int] = (160, 120)) -> Image.Image:
    """Deterministic RGB noise. Same seed -> identical (phash distance 0);
    different seed -> high-frequency noise (large phash distance)."""
    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    img.putdata([(rnd.randint(0, 255),) * 3 for _ in range(size[0] * size[1])])
    return img


class FakeClock:
    def __init__(self, start: dt.datetime) -> None:
        self._now = start

    def now(self) -> dt.datetime:
        return self._now

    def sleep(self, seconds: float) -> None:
        self._now += dt.timedelta(seconds=seconds)

    def advance(self, seconds: float) -> None:
        self._now += dt.timedelta(seconds=seconds)


class FakeScreenshotAdapter:
    def __init__(self) -> None:
        self.image = make_image(1)
        self.monitor_index = 1
        self.raise_next = False
        self.permission = PermissionStatus.OK

    def capture_monitor_of(self, win: WindowInfo | None) -> Capture:
        if self.raise_next:
            self.raise_next = False
            raise RuntimeError("boom")
        return Capture(image=self.image, monitor_index=self.monitor_index, physical_scale=1.0)

    def preflight(self) -> PermissionStatus:
        return self.permission


class FakeActiveWindowAdapter:
    def __init__(self, window: WindowInfo | None = None) -> None:
        self.window = window or WindowInfo(app_name="chrome.exe", window_title="タブ", pid=1)

    def get_active_window(self) -> WindowInfo | None:
        return self.window


class FakeIdleAdapter:
    def __init__(self) -> None:
        self.seconds = 0.0

    def seconds_since_input(self) -> float:
        return self.seconds


class FakeTrayAdapter:
    def __init__(self) -> None:
        self.status = ""
        self.ran = False

    def run(self, menu: TrayMenuSpec) -> None:
        self.ran = True

    def update_status(self, text: str) -> None:
        self.status = text

    def stop(self) -> None:
        self.ran = False


class FakeHotkeyAdapter:
    def __init__(self) -> None:
        self.combo = None
        self.callback = None

    def register(self, combo, on_press) -> bool:
        self.combo = combo
        self.callback = on_press
        return True


def make_fake_adapters() -> Adapters:
    return Adapters(
        screenshot=FakeScreenshotAdapter(),
        active_window=FakeActiveWindowAdapter(),
        idle=FakeIdleAdapter(),
        tray=FakeTrayAdapter(),
        hotkey=FakeHotkeyAdapter(),
    )
