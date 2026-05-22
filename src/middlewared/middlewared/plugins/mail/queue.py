from __future__ import annotations

from collections import deque
from email.mime.base import MIMEBase
from threading import Lock
from typing import Any


class QueueItem:
    def __init__(self, message: MIMEBase) -> None:
        self.attempts = 0
        self.message = message


class MailQueue:
    MAX_ATTEMPTS = 3
    MAX_QUEUE_LIMIT = 20

    def __init__(self) -> None:
        self.queue: deque[QueueItem] = deque(maxlen=self.MAX_QUEUE_LIMIT)
        self.lock = Lock()

    def append(self, message: MIMEBase) -> None:
        self.queue.append(QueueItem(message))

    def __enter__(self) -> MailQueue:
        self.lock.acquire()
        return self

    def __exit__(self, typ: Any, value: Any, traceback: Any) -> None:
        self.lock.release()
        if typ is not None:
            raise
