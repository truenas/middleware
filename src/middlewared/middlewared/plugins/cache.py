from collections.abc import Callable
from enum import StrEnum
from time import monotonic, time
from typing import Any

from middlewared.service import periodic, Service
from middlewared.service_exception import MatchNotFound
from middlewared.utils import MIDDLEWARE_BOOT_ENV_STATE_DIR
from middlewared.utils.tdb import (
    TDBBatchAction, TDBBatchOperation, TDBPathType, TDBOptions, TDBDataType, get_tdb_handle
)


CACHE_LOCAL_PERSISTENT_OPTS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.JSON)
CACHE_LOCAL_VOLATILE_OPTS = TDBOptions(TDBPathType.VOLATILE, TDBDataType.JSON)
CACHE_CLUSTER_OPTS = TDBOptions(TDBPathType.PERSISTENT, TDBDataType.JSON, True)
LOCAL_PERSISTENT_PATH = f'{MIDDLEWARE_BOOT_ENV_STATE_DIR}/middlewared_cache'


class CacheType(StrEnum):
    VOLATILE = "VOLATILE"
    PERSISTENT = "PERSISTENT"
    CLUSTERED = "CLUSTERED"


class KVCache:
    """ Cache that persists across middleware restarts, but not system upgrades. """
    def __init__(self, path: str, tdb_options: TDBOptions, time_fn: Callable):
        """
        Initialize persistent cache.

        Args:
            path: Path to the TDB file
            tdb_options: TDB configuration options
        """
        self.tdb_options = tdb_options
        self.path = path
        self.time_fn = time_fn

    def has_key(self, key: str) -> bool:
        """Check if given `key` exists in persistent cache."""
        with get_tdb_handle(self.path, self.tdb_options) as hdl:
            try:
                hdl.get(key)
            except (FileNotFoundError, MatchNotFound):
                return False
            else:
                return True

    def get(self, key: str) -> Any:
        """
        Get `key` from persistent cache.

        Raises:
            KeyError: not found in the cache or has expired
        """
        with get_tdb_handle(self.path, self.tdb_options) as hdl:
            try:
                data = hdl.get(key)
            except (FileNotFoundError, MatchNotFound):
                raise KeyError(key)

            if data['timeout'] and self.time_fn() > data['timeout']:
                hdl.delete(key)
                raise KeyError(f"{key} has expired")

            return data['value']

    def put(self, key: str, value: Any, timeout: int = 0) -> None:
        """
        Put `key` with `value` in the persistent cache.

        Args:
            key: Cache key
            value: Value to cache
            timeout: Optional expiration timeout in seconds (0 = no expiration)
        """
        with get_tdb_handle(self.path, self.tdb_options) as hdl:
            if timeout != 0:
                timeout = self.time_fn() + timeout

            hdl.store(key, {'timeout': timeout, 'value': value})

    def pop(self, key: str) -> Any:
        """
        Remove and return `key` from persistent cache.

        Performs a fetch and delete under transaction lock to ensure atomicity.

        Returns:
            The cached value, or None if key not found or operation fails.
        """
        batch_ops = [
            TDBBatchOperation(
                action=TDBBatchAction.GET,
                key=key,
            ),
            TDBBatchOperation(
                action=TDBBatchAction.DEL,
                key=key,
            )
        ]

        with get_tdb_handle(self.path, self.tdb_options) as hdl:
            try:
                result = hdl.batch_op(batch_ops)
            except Exception:
                return None

            return result[key]['value']

    def get_timeout(self, key: str) -> None:
        """
        Check if `key` has expired and remove it if so.

        Raises:
            KeyError: if key has expired or not found (also removes it from cache)
        """
        self.get(key)

    def get_or_put(self, key: str, timeout: int, method: Callable) -> Any:
        """
        Get `key` from persistent cache, or call `method` to generate value if not found.

        If key exists and is not expired, returns cached value.
        Otherwise, calls method() to generate a new value, caches it, and returns it.

        NOTE: This operation is atomic for the local persistent cache, but not for clustered cache.
        More design work will be required if atomicity is needed on clustered database.
        """
        call_method = False

        with get_tdb_handle(self.path, self.tdb_options) as hdl:
            try:
                data = hdl.get(key)
            except (FileNotFoundError, MatchNotFound):
                call_method = True
            else:
                if data['timeout'] and self.time_fn() > data['timeout']:
                    call_method = True

            if call_method:
                value = method()
                hdl.store(key, {'timeout': self.time_fn() + timeout, 'value': value})
            else:
                value = data['value']

        return value

    def cleanup_expired(self) -> None:
        to_del = []
        now = self.time_fn()

        with get_tdb_handle(self.path, self.tdb_options) as hdl:
            for entry in hdl.entries():
                if entry['value']['timeout'] and now > entry['value']['timeout']:
                    to_del.append(entry['key'])

            for key in to_del:
                hdl.delete(key)

            hdl.vacuum()


class CacheService(Service):
    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(CacheService, self).__init__(*args, **kwargs)
        self.volatile = KVCache('middleware_cache', CACHE_LOCAL_VOLATILE_OPTS, monotonic)
        self.persistent = KVCache(LOCAL_PERSISTENT_PATH, CACHE_LOCAL_PERSISTENT_OPTS, time)
        self.cluster = KVCache('middleware_cache', CACHE_CLUSTER_OPTS, time)

    def __get_cache(self, cache_type: CacheType) -> KVCache:
        match cache_type:
            case CacheType.VOLATILE:
                return self.volatile
            case CacheType.PERSISTENT:
                return self.persistent
            case CacheType.CLUSTER:
                return self.cluster
            case _:
                raise ValueError(f'{cache_type}: unexpected cache type')

    def has_key(self, key: str, cache_type: CacheType = CacheType.VOLATILE):
        """Check if given `key` is in cache."""
        cache = self.__get_cache(cache_type)
        return cache.has_key(key)

    def get(self, key: str, cache_type: CacheType = CacheType.VOLATILE):
        """
        Get `key` from cache.

        Raises:
            KeyError: not found in the cache
        """
        cache = self.__get_cache(cache_type)
        return cache.get(key)

    def put(self, key: str, value: Any, timeout: int = 0, cache_type: CacheType = CacheType.VOLATILE):
        """Put `key` of `value` in the cache."""
        cache = self.__get_cache(cache_type)
        return cache.put(key, value, timeout)

    def pop(self, key: str, cache_type: CacheType = CacheType.VOLATILE):
        """Removes and returns `key` from cache."""
        cache = self.__get_cache(cache_type)
        return cache.pop(key)

    def get_timeout(self, key: str, cache_type: CacheType = CacheType.VOLATILE):
        """Check if 'key' has expired"""
        cache = self.__get_cache(cache_type)
        return cache.get_timeout(key)

    def get_or_put(self, key: str, timeout: int, method: Callable, cache_type: CacheType = CacheType.VOLATILE):
        cache = self.__get_cache(cache_type)
        return cache.get_or_put(key, timeout, method)

    @periodic(86400, run_on_start=False)
    def cleanup_expired(self):
        """ internal method to clear out any expired keys from caches to prevent unbounded growth """
        failover_licensed = self.middleware.call_sync('failover.licensed')

        for cache in CacheType:
            if not failover_licensed and cache is CacheType.CLUSTERED:
                continue

            hdl = self.__get_cache(cache)
            try:
                hdl.cleanup_expired()
            except Exception:
                self.logger.exception('%s: failed to cleanup expired cache entries', cache)
