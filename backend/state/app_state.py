from __future__ import annotations
import asyncio
import threading
from datetime import datetime, timezone
from typing import Any, Optional, Callable

from config import ServerConfig


class AppState:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.ied_server: Any = None
        self.ied_model: Any = None
        self.da_cache: dict[str, Any] = {}
        self.config: ServerConfig = ServerConfig()
        self.scl_source: str = "default"
        self.start_time: Optional[datetime] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_broadcaster: Optional[Callable] = None

    def broadcast(self, message: dict) -> None:
        if self._ws_broadcaster and self.event_loop and not self.event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._ws_broadcaster(message), self.event_loop)

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self.ied_server is not None

    @property
    def uptime_seconds(self) -> Optional[float]:
        with self._lock:
            if self.start_time is None:
                return None
            return (datetime.now(timezone.utc) - self.start_time).total_seconds()
