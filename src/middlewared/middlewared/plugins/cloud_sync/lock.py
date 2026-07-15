from __future__ import annotations

from contextlib import contextmanager
import enum
import os
import threading
from typing import Any, Iterator


class FsLockDirection(enum.Enum):
    READ = 0
    WRITE = 1


class SyncRWLock:
    """Synchronous read-write lock implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._readers = 0
        self._writers = 0
        self._fs_manager: FsLockManager | None = None
        self._fs_path: str | None = None

    @contextmanager
    def reader_lock(self) -> Iterator[None]:
        """Context manager for acquiring read lock."""
        with self._lock:
            while self._writers > 0:
                self._read_ready.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._lock:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notify_all()
                    if self._fs_manager and self._writers == 0:
                        self._fs_manager._remove_lock(self._fs_path)

    @contextmanager
    def writer_lock(self) -> Iterator[None]:
        """Context manager for acquiring write lock."""
        with self._lock:
            while self._writers > 0 or self._readers > 0:
                self._read_ready.wait()
            self._writers += 1
        try:
            yield
        finally:
            with self._lock:
                self._writers -= 1
                self._read_ready.notify_all()
                if self._fs_manager and self._readers == 0:
                    self._fs_manager._remove_lock(self._fs_path)


class FsLockManager:
    def __init__(self) -> None:
        self.sync_locks: dict[str, SyncRWLock] = {}

    def lock(self, path: str, direction: FsLockDirection) -> Any:
        """Return a synchronous lock context manager."""
        path = os.path.normpath(path)
        for k in self.sync_locks:
            if os.path.commonpath([k, path]) in [k, path]:
                return self._choose_sync_lock(self.sync_locks[k], direction)

        self.sync_locks[path] = SyncRWLock()
        self.sync_locks[path]._fs_manager = self
        self.sync_locks[path]._fs_path = path
        return self._choose_sync_lock(self.sync_locks[path], direction)

    def _choose_lock(self, lock: SyncRWLock, direction: FsLockDirection) -> Any:
        if direction == FsLockDirection.READ:
            return lock.reader_lock
        if direction == FsLockDirection.WRITE:
            return lock.writer_lock
        raise ValueError(direction)

    def _choose_sync_lock(self, lock: SyncRWLock, direction: FsLockDirection) -> Any:
        if direction == FsLockDirection.READ:
            return lock.reader_lock()
        if direction == FsLockDirection.WRITE:
            return lock.writer_lock()
        raise ValueError(direction)

    def _remove_lock(self, path: str | None) -> None:
        if path is not None:
            self.sync_locks.pop(path, None)


# Process-wide singletons shared by every cloud sync job (mirrors the class attributes the
# monolithic `CloudSyncService` used to hold).
local_fs_lock_manager = FsLockManager()
remote_fs_lock_manager = FsLockManager()
