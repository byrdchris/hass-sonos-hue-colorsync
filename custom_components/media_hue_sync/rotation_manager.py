from __future__ import annotations

# Color rotation lifecycle and timing manager.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

from .const import (
    AUTO_ROTATE_SAFETY_BUFFER_SECONDS,
    CONF_AUTO_ROTATE_COLORS,
    CONF_AUTO_ROTATE_INTERVAL,
    CONF_ROTATION_MODE,
    CONF_TRANSITION,
    DEFAULT_AUTO_ROTATE_INTERVAL,
    DEFAULT_ROTATION_MODE,
    DEFAULT_TRANSITION,
    MAX_AUTO_ROTATE_INTERVAL,
    MIN_AUTO_ROTATE_INTERVAL,
    ROTATION_MODE_AUTO,
    ROTATION_MODE_OFF,
    ROTATION_MODE_TRACK_AND_AUTO,
    ROTATION_MODE_TRACK_CHANGE,
)

_LOGGER = logging.getLogger(__name__)


class RotationManager:
    """Manages continuous color rotation scheduling, timers, and wake events."""

    def __init__(
        self,
        hass: Any,
        get_coordinator_state: Callable[[], dict[str, Any]],
        apply_rotation_callback: Callable[[], Coroutine[Any, Any, None]],
        notify_callback: Callable[[], None],
    ) -> None:
        self.hass = hass
        self._get_coordinator_state = get_coordinator_state
        self._apply_rotation_callback = apply_rotation_callback
        self._notify = notify_callback

        self._auto_rotate_task: asyncio.Task | None = None
        self._auto_rotate_wake_event = asyncio.Event()
        self.last_auto_rotation_started: str | None = None
        self.last_auto_rotation_completed: str | None = None
        self.last_auto_rotation_skipped_reason: str | None = None
        self.last_auto_rotation_timing: dict[str, Any] = {}

    def is_allowed(self) -> bool:
        """Return True if continuous rotation is enabled, player is active, and palette exists."""
        state = self._get_coordinator_state()
        if not state.get("enabled", False):
            return False
        if not state.get("sonos_is_active", False):
            return False
        if not state.get("last_palette"):
            return False

        config = state.get("config", {})
        rotation_mode = config.get(CONF_ROTATION_MODE, DEFAULT_ROTATION_MODE)
        if rotation_mode == ROTATION_MODE_OFF:
            return False
        if rotation_mode in (ROTATION_MODE_AUTO, ROTATION_MODE_TRACK_AND_AUTO):
            return True
        if rotation_mode == ROTATION_MODE_TRACK_CHANGE:
            return False
        return bool(config.get(CONF_AUTO_ROTATE_COLORS, False))

    def rotation_timing(self) -> dict[str, Any]:
        """Calculate effective cycle, hold time, and safety buffers."""
        state = self._get_coordinator_state()
        config = state.get("config", {})
        interval = float(config.get(CONF_AUTO_ROTATE_INTERVAL, DEFAULT_AUTO_ROTATE_INTERVAL) or DEFAULT_AUTO_ROTATE_INTERVAL)
        transition = float(config.get(CONF_TRANSITION, DEFAULT_TRANSITION) or DEFAULT_TRANSITION)
        safety_buffer = float(AUTO_ROTATE_SAFETY_BUFFER_SECONDS)
        bounded_interval = max(MIN_AUTO_ROTATE_INTERVAL, min(MAX_AUTO_ROTATE_INTERVAL, interval))
        effective_cycle = max(bounded_interval, transition + safety_buffer)
        hold_time = max(0.0, effective_cycle - transition)
        limited_by_transition = bool(effective_cycle > bounded_interval)

        return {
            "configured_interval_seconds": bounded_interval,
            "transition_seconds": transition,
            "safety_buffer_seconds": safety_buffer,
            "calculated_hold_seconds": round(hold_time, 3),
            "effective_cycle_seconds": round(effective_cycle, 3),
            "limited_by_transition": limited_by_transition,
        }

    def wake(self) -> None:
        """Signal the rotation loop to recheck settings immediately."""
        self._auto_rotate_wake_event.set()

    def start_if_needed(self) -> None:
        """Start the rotation background task if conditions are met."""
        if not self.is_allowed():
            self.stop()
            return
        if self._auto_rotate_task is None or self._auto_rotate_task.done():
            self._auto_rotate_wake_event.clear()
            self._auto_rotate_task = self.hass.loop.create_task(self._auto_rotate_loop())

    def stop(self) -> None:
        """Cancel and clean up the background rotation task."""
        if self._auto_rotate_task is not None:
            self._auto_rotate_task.cancel()
            self._auto_rotate_task = None
        self._auto_rotate_wake_event.set()

    async def _auto_rotate_wait(self, seconds: float) -> bool:
        """Wait for auto-rotation timing, waking early on option changes."""
        if seconds <= 0:
            return False

        deadline = time.monotonic() + seconds
        while self.is_allowed():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            self._auto_rotate_wake_event.clear()
            try:
                await asyncio.wait_for(
                    self._auto_rotate_wake_event.wait(),
                    timeout=min(1.0, remaining),
                )
                return True
            except asyncio.TimeoutError:
                continue
        return False

    async def _wait_for_apply_idle(self) -> bool:
        """Wait briefly for a current light update to finish before rotating."""
        while self._get_coordinator_state().get("apply_in_progress", False):
            self.last_auto_rotation_skipped_reason = "waiting_for_active_light_update"
            self._notify()
            changed = await self._auto_rotate_wait(0.25)
            if changed or not self.is_allowed():
                return False
        return True

    async def _auto_rotate_loop(self) -> None:
        """Continuous rotation loop."""
        try:
            while self.is_allowed():
                timing = self.rotation_timing()
                self.last_auto_rotation_timing = timing
                self.last_auto_rotation_skipped_reason = None
                self._notify()

                changed = await self._auto_rotate_wait(timing["effective_cycle_seconds"])
                if changed or not self.is_allowed():
                    continue

                if not await self._wait_for_apply_idle() or not self.is_allowed():
                    continue

                self.last_auto_rotation_started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self.last_auto_rotation_skipped_reason = None
                self._notify()
                await self._apply_rotation_callback()
                self.last_auto_rotation_completed = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._notify()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.last_auto_rotation_skipped_reason = f"error:{type(err).__name__}"
            _LOGGER.exception("Continuous color rotation failed: %s", err)
            self._notify()
        finally:
            self._auto_rotate_task = None
            self._notify()
