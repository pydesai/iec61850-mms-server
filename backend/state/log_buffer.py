from __future__ import annotations
import asyncio
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel


class LogEntry(BaseModel):
    level: str  # ERROR, WARN, INFO, DEBUG
    message: str
    timestamp: str
    raw_hex: Optional[str] = None


class LogBuffer:
    def __init__(self, maxlen: int = 10_000):
        self._entries: deque[LogEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._subscribers: list[asyncio.Queue] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def append(self, level: str, message: str, raw_bytes: Optional[bytes] = None) -> None:
        entry = LogEntry(
            level=level,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            raw_hex=raw_bytes.hex() if raw_bytes else None,
        )
        with self._lock:
            self._entries.append(entry)
            subscribers = list(self._subscribers)

        if self._loop and not self._loop.is_closed():
            for q in subscribers:
                try:
                    self._loop.call_soon_threadsafe(q.put_nowait, entry)
                except Exception:
                    pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def get_all(
        self,
        level: Optional[str] = None,
        limit: int = 500,
        since: Optional[str] = None,
    ) -> list[LogEntry]:
        with self._lock:
            entries = list(self._entries)

        if level and level != "ALL":
            entries = [e for e in entries if e.level == level]

        if since:
            entries = [e for e in entries if e.timestamp > since]

        return entries[-limit:]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
