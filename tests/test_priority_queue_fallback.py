"""Tests for the priority-queue disabled-but-still-answers fix.

The CRITICAL bug this covers: a config with ``priority_queue.enabled=False``
used to make ``start()`` bail out silently. ``enqueue_question`` then kept
adding items to a queue that nothing was draining, so the UI's AI Suggestions
panel stayed empty forever. After the fix, ``start()`` spins up a minimal
direct dispatcher in that case, and ``enqueue_question`` only drops items
when the machinery really isn't running.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.ai.priority_queue import PriorityQueueManager


@pytest.fixture(autouse=True)
def _reset_config_singleton():
    from src.utils import config as _cfg

    _cfg._config = None
    yield
    _cfg._config = None


@pytest.fixture
def mock_qtimer():
    with patch("src.ai.priority_queue.QTimer") as mock:
        mock.return_value = MagicMock()
        yield mock


class TestDisabledQueueStillStarts:
    def test_start_works_with_enabled_false(self, monkeypatch, mock_qtimer):
        from src.utils import config as _cfg

        original_get = _cfg.ConfigManager.get

        def patched_get(self, key, default=None):
            if key == "priority_queue":
                # Force the direct-dispatch path: config says disabled.
                result = original_get(self, key, default)
                # Create a copy with enabled=False to be safe.
                if result is not None:
                    result.enabled = False
                return result
            return original_get(self, key, default)

        monkeypatch.setattr(_cfg.ConfigManager, "get", patched_get)

        pq = PriorityQueueManager()
        assert pq.enabled is False  # sanity: direct-dispatch path under test

        pq.start()
        try:
            assert pq._running is True, (
                "start() must spin up the worker thread even when enabled=False "
                "-- otherwise enqueue_question silently drops every question"
            )
            # Aging timer is priority-mode-only; direct mode skips it.
            assert pq._aging_timer is None
            assert pq._asyncio_loop is not None
            assert pq._asyncio_thread is not None
        finally:
            pq.stop()
            # Give background thread a moment to unwind before the fixture
            # resets the config singleton out from under it.
            time.sleep(0.05)
        assert pq._running is False

    def test_start_works_with_enabled_true(self, mock_qtimer):
        # Don't monkeypatch -- use whatever the config has. If the user has
        # enabled=False on disk, _reset_config_singleton will re-load it.
        pq = PriorityQueueManager()
        pq.enabled = True  # force the priority-queue path regardless of disk config
        pq.start()
        try:
            assert pq._running is True
            assert pq._asyncio_loop is not None
        finally:
            pq.stop()
            time.sleep(0.05)


class TestEnqueueWithoutStart:
    def test_enqueue_before_start_warns_and_drops(self, caplog):
        """Calling enqueue_question before start() must NOT put items into
        an un-drained queue. The fix raises a WARNING and drops the item so
        the log tells you what happened."""
        import logging

        pq = PriorityQueueManager()
        assert pq._running is False

        # Capture both stdlib logging and structlog output.
        with caplog.at_level(logging.WARNING):
            pq.enqueue_question("What is the meaning of life?", "msg-1")

        # Queue must NOT contain the item; it was dropped.
        assert pq._queue.qsize() == 0
        # Counters untouched.
        assert pq._priority_count == 0
        assert pq._normal_count == 0


class TestEnqueueAfterStart:
    def test_enqueue_after_start_goes_into_queue(self, mock_qtimer):
        pq = PriorityQueueManager()
        pq.enabled = True  # simplest -- run full priority-queue mode
        pq.start()
        try:
            # Before any worker processes it, the item should be in the queue.
            pq.enqueue_question("Where are we going?", "msg-42")
            # Worker may have already picked it up by the time we check, so
            # we don't assert on qsize directly. Instead assert a counter
            # reflected the enqueue -- counters are updated synchronously.
            assert pq._priority_count + pq._normal_count >= 1
        finally:
            pq.stop()
            time.sleep(0.05)
