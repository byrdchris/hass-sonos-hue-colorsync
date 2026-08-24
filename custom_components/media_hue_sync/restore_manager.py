from __future__ import annotations

# Scene snapshot and restore manager.
# brief-code-commented-build: moderate block-level comments added for maintainability.

import asyncio
import logging
from typing import Any, Callable

from .applier import clear_apply_cache
from .hue_controller import _snapshot_count, restore_scene, snapshot_scene

_LOGGER = logging.getLogger(__name__)


class RestoreManager:
    """Manages light scene snapshotting and restore lifecycle."""

    def __init__(self, hass: Any, notify_callback: Callable[[], None]) -> None:
        self.hass = hass
        self._notify = notify_callback

        self.scene: dict[str, Any] | None = None
        self._restore_delay_task: asyncio.Task | None = None
        self.last_restore_result: dict[str, Any] | str | None = None
        self.last_restore_snapshot_count: int = 0
        self.last_restore_reason: str | None = None

    async def capture_snapshot(self, targets: list[str], reason: str = "snapshot") -> None:
        """Capture target light state before Media Hue Sync changes anything."""
        if not targets:
            self.scene = None
            self.last_restore_snapshot_count = 0
            self.last_restore_result = "no_targets_to_snapshot"
            self.last_restore_reason = reason
            return

        self.scene = await snapshot_scene(self.hass, targets)
        self.last_restore_snapshot_count = _snapshot_count(self.scene)
        self.last_restore_result = "snapshot_captured"
        self.last_restore_reason = reason

    def cancel_pending_restore(self, reason: str = "cancelled") -> None:
        """Cancel an in-flight delayed restore task."""
        if self._restore_delay_task is not None and not self._restore_delay_task.done():
            self.last_restore_result = {"status": "cancelled", "reason": reason}
            self._restore_delay_task.cancel()
        self._restore_delay_task = None

    async def restore_snapshot_now(self, reason: str = "restore", clear_snapshot: bool = True) -> dict[str, Any]:
        """Restore the captured light snapshot immediately."""
        self.last_restore_reason = reason
        if not self.scene:
            self.last_restore_snapshot_count = 0
            result = {"status": "no_snapshot", "reason": reason}
            self.last_restore_result = result
            clear_apply_cache()
            self._notify()
            return result

        try:
            self.last_restore_snapshot_count = _snapshot_count(self.scene)
            restore_result = await restore_scene(self.hass, self.scene)
            restore_result["status"] = "restored"
            restore_result["reason"] = reason
            self.last_restore_result = restore_result
            if clear_snapshot:
                self.scene = None
        except Exception as err:
            self.last_restore_result = {"status": "failed", "reason": reason, "failed": str(err)}
            _LOGGER.exception("Failed restoring Media Hue Sync scene: %s", err)

        clear_apply_cache()
        self._notify()
        return self.last_restore_result if isinstance(self.last_restore_result, dict) else {"status": "restored"}

    async def restore_after_delay(self, delay: float, reason: str = "playback_stopped") -> None:
        """Delay scene restore after playback stops."""
        try:
            if delay > 0:
                self.last_restore_result = {"status": "pending", "reason": reason, "delay_seconds": delay}
                self._notify()
                await asyncio.sleep(delay)
            await self.restore_snapshot_now(reason=reason, clear_snapshot=True)
        except asyncio.CancelledError:
            if not isinstance(self.last_restore_result, dict) or self.last_restore_result.get("status") != "cancelled":
                self.last_restore_result = {"status": "cancelled", "reason": reason}
                self._notify()
            raise

    def handle_stop(self, delay: float, reason: str = "playback_stopped") -> None:
        """Schedule a delayed restore on playback stop."""
        self.last_restore_reason = reason
        self.cancel_pending_restore(reason=f"new_restore_request:{reason}")
        self._restore_delay_task = self.hass.loop.create_task(self.restore_after_delay(delay, reason=reason))
        self.last_restore_result = {"status": "pending", "reason": reason, "delay_seconds": delay}
        self._notify()
