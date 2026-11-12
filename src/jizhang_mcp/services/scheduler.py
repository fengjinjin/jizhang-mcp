import asyncio
import logging

from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.services.recurring_service import settle_due_rules

logger = logging.getLogger("jizhang")


class RecurringScheduler:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        factory = get_session_factory()
        while not self._stop.is_set():
            try:
                async with factory() as session:
                    await settle_due_rules(session)
            except Exception:
                logger.exception("scheduler tick failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue
