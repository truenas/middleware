from base64 import b64decode, b64encode
import binascii
from collections import defaultdict, namedtuple
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
import enum
import os
from threading import RLock
from typing import Any, Literal, overload

import tdb
from truenas_api_client import ejson as json

from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH
from middlewared.service_exception import MatchNotFound

FD_CLOSED = -1
# Robust mutex support was added to libtdb after py-tdb was written and flags
# weren't updated. See lib/tdb/include/tdb.h
MUTEX_LOCKING = 4096

TDB_LOCKS: defaultdict[str, RLock] = defaultdict(RLock)
TDBOptions = namedtuple('TDBOptions', ['backend', 'data_type'])
TDB_HANDLES: dict[str, 'TDBHandle'] = {}


class TDBPathType(enum.Enum):
    """
    Type of path for TDB file

    VOLATILE - cleared on reboot (tmpfs)

    PERSISTENT - persist across reboots

    CUSTOM - arbitrary filesystem path (used for interacting with service TDB files)
    """
    VOLATILE = '/var/run/tdb/volatile'
    PERSISTENT = '/root/tdb/persistent'
    CUSTOM = ''


class TDBDataType(enum.Enum):
    """
    Types of data to encode in TDB file

    RAW - binary data submitted and returned as python bytes. This is the appropriate
    type for interacting with TDB files used by 3rd party applications from within
    middleware.

    BYTES - binary data. API consumer submits as b64encoded string that is decoded before insertion.
    Prefer RAW unless the value is read or written by an API consumer, since base64 is a
    transport encoding rather than a property of the database.

    JSON - submit as python dictionary and converted into JSON before insertion

    STRING - submit as python string and inserted as-is
    """
    RAW = enum.auto()
    BYTES = enum.auto()
    JSON = enum.auto()
    STRING = enum.auto()


class TDBBatchAction(enum.Enum):
    """ Types of actions to use for batch operations """
    GET = enum.auto()
    SET = enum.auto()
    DEL = enum.auto()


class TDBError(enum.IntEnum):
    """ TDB errors are included in RuntimeError raised by TDB library """
    SUCCESS = 0
    CORRUPT = enum.auto()
    IO = enum.auto()
    LOCK = enum.auto()
    OOM = enum.auto()
    EXISTS = enum.auto()
    NOLOCK = enum.auto()
    TIMEOUT = enum.auto()
    NOEXIST = enum.auto()
    EINVAL = enum.auto()
    RDONLY = enum.auto()
    NESTING = enum.auto()


@dataclass
class TDBBatchOperation:
    """
    Dataclass for batch operation on TDB file

    key - target TDB key

    value - value to set. This is required for SET operations,
    but not evaluated for GET and DEL operations.
    """
    action: TDBBatchAction
    key: str
    value: str | bytes | dict[str, Any] | None = None


def keys_are_null_terminated(name: str, data_type: TDBDataType) -> bool:
    """
    Whether the on-disk keys of the TDB database identified by `name` carry a
    trailing NUL terminator.

    ``secrets.tdb`` is the odd one out: unlike most samba databases (which key via
    ``string_term_tdb_data()`` == ``strlen + 1``) its keys have no terminator.
    """
    match os.path.basename(name):
        case 'gencache.tdb':
            return True
        case 'secrets.tdb':
            return False
        case 'group_mapping.tdb' | 'group_mapping_rejects.tdb' | 'passdb.tdb':
            return True
        case _:
            # Most samba tdb files use NULL-terminated string keys; middleware-owned
            # databases that store JSON/STRING values do not.
            return data_type in (TDBDataType.RAW, TDBDataType.BYTES)


class TDBHandle:
    hdl: Any = None
    name: str | None = None
    data_type: TDBDataType | None = None
    path_type: TDBPathType | None = None
    full_path: str | None = None
    keys_null_terminated: bool = False

    def __enter__(self) -> 'TDBHandle':
        return self

    def __exit__(self, tp: type[BaseException] | None, val: BaseException | None, traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        """ Close the TDB handle """
        if self.hdl is not None:
            self.hdl.close()
            self.hdl = None

    def validate_handle(self) -> bool:
        """
        Check whether the TDB handle is still valid
        If it is invalid, then a new handle object should be created.
        """
        if not self.hdl or self.hdl.fd == FD_CLOSED:
            return False

        if not os.path.exists(f'/proc/self/fd/{self.hdl.fd}'):
            return False

        # if file has been renamed or deleted from under us, readlink will show different path
        return os.readlink(f'/proc/self/fd/{self.hdl.fd}') == self.full_path

    def parse_value(self, tdb_val: bytes) -> dict[str, Any] | str | bytes:
        out: dict[str, Any] | str | bytes

        match self.data_type:
            case TDBDataType.RAW:
                out = tdb_val
            case TDBDataType.BYTES:
                out = b64encode(tdb_val).decode()
            case TDBDataType.JSON:
                out = json.loads(tdb_val.decode())
            case TDBDataType.STRING:
                out = tdb_val.decode()
            case _:
                raise ValueError(f'{self.data_type}: unknown data type')

        return out

    def flush(self) -> None:
        """ Ensure sync of file to disk """
        os.fdatasync(self.hdl.fd)

    def get(self, key: str) -> dict[str, Any] | str | bytes:
        """
        Retrieve the specified key

        Returns:
            bytes if TDBDataType is RAW
            dict if TDBDataType is JSON
            str if TDBDataType is BYTES or STRING

        Raises:
            MatchNotFound
            RuntimeError
        """
        tdb_key = key.encode()
        if self.keys_null_terminated:
            tdb_key += b"\x00"

        if (tdb_val := self.hdl.get(tdb_key)) is None:
            raise MatchNotFound(key)

        return self.parse_value(tdb_val)

    def encode_value(self, value: str | dict[str, Any] | bytes) -> bytes:
        """
        Convert `value` into the bytes to be written for this database's data type.

        The type a caller must supply follows from `data_type` rather than from any
        signature, and so cannot be expressed to a type checker. It is checked here to
        keep a mismatch from reaching the database: b64decode() is asked to validate
        because it otherwise discards everything outside its alphabet before checking
        padding, and stores a truncated record instead of failing.

        Raises:
            TypeError
            ValueError
        """
        match self.data_type:
            case TDBDataType.RAW:
                if not isinstance(value, bytes):
                    raise TypeError(f'{type(value).__name__}: RAW values must be bytes')

                return value
            case TDBDataType.BYTES:
                # bytes are accepted because b64encode() output is not decoded by most callers
                if not isinstance(value, (str, bytes)):
                    raise TypeError(f'{type(value).__name__}: BYTES values must be base64-encoded')

                try:
                    return b64decode(value, validate=True)
                except binascii.Error as exc:
                    raise ValueError(f'BYTES values must be base64-encoded: {exc}') from exc
            case TDBDataType.JSON:
                if not isinstance(value, dict):
                    raise TypeError(f'{type(value).__name__}: JSON values must be a dict')

                return json.dumps(value).encode()
            case TDBDataType.STRING:
                if not isinstance(value, str):
                    raise TypeError(f'{type(value).__name__}: STRING values must be a str')

                return value.encode()
            case _:
                raise ValueError(f'{self.data_type}: unknown data type')

    def store(self, key: str, value: str | dict[str, Any] | bytes) -> None:
        """
        Set the specified `key` to the specified `value`.

        Raises:
            RuntimeError
            TypeError
            ValueError
        """
        tdb_key = key.encode()
        if self.keys_null_terminated:
            tdb_key += b'\x00'

        self.hdl.store(tdb_key, self.encode_value(value))

    def delete(self, key: str) -> None:
        """
        Delete the specified `key`

        Raises:
            RuntimeError
        """
        tdb_key = key.encode()
        if self.keys_null_terminated:
            tdb_key += b"\x00"

        self.hdl.delete(tdb_key)

    def clear(self) -> None:
        """
        Clear all entries from the specified TDB file

        Raises:
            RuntimeError
        """
        self.hdl.clear()

    @overload
    def entries(self, include_keys: Literal[True] = ..., key_prefix: str | None = None) -> Iterable[dict[str, Any]]: ...

    @overload
    def entries(self, include_keys: Literal[False] = ..., key_prefix: str | None = None) -> (
        Iterable[dict[str, Any] | str | bytes]
    ): ...

    def entries(
        self, include_keys: bool = True, key_prefix: str | None = None
    ) -> Iterable[dict[str, Any] | str | bytes]:
        """
        Iterate entries in TDB file:

        include_keys - yield entries as dictionary containing `key` and `value`
        otherwise only value will be yielded.

        value - may be str or dict

        Raises:
            RuntimeError
        """
        for key in self.hdl.keys():
            tdb_key = key.decode()
            if self.keys_null_terminated:
                tdb_key = tdb_key[:-1]

            if key_prefix and not tdb_key.startswith(key_prefix):
                continue

            tdb_val = self.get(tdb_key)
            if include_keys:
                yield {
                    'key': tdb_key,
                    'value': tdb_val
                }
            else:
                yield tdb_val

    def batch_op(self, ops: list[TDBBatchOperation]) -> dict[str, Any]:
        """
        Perform a list of operations under a transaction lock so that
        they are automatically rolled back if any one of operations fails.

        Returns:
            dictionary containing results of all `GET` operations.

        Raises:
            RuntimeError
            MatchNotFound
            ValueError
        """
        output = {}
        try:
            self.hdl.transaction_start()
        except RuntimeError:
            self.close()
            raise

        try:
            for op in ops:
                match op.action:
                    case TDBBatchAction.SET:
                        if op.value is None:
                            raise ValueError(f'{op.key}: SET operation requires a value')

                        self.store(op.key, op.value)
                    case TDBBatchAction.DEL:
                        self.delete(op.key)
                    case TDBBatchAction.GET:
                        output[op.key] = self.get(op.key)
                    case _:
                        raise ValueError(f'{op.action}: unknown batch operation type')

            self.hdl.transaction_commit()
        except Exception:
            self.hdl.transaction_cancel()
            raise

        return output

    def vacuum(self) -> None:
        """ Repack the database to free up space """
        self.hdl.repack()

    def __init__(
        self,
        name: str,
        options: TDBOptions
    ):
        self.name = name
        self.path_type = TDBPathType(options.backend)
        self.data_type = TDBDataType(options.data_type)

        match os.path.basename(name):
            case 'gencache.tdb':
                # See gencache_init() in source3/lib/gencache.c in Samba
                tdb_flags = tdb.INCOMPATIBLE_HASH | tdb.NOSYNC | MUTEX_LOCKING
                open_flags = os.O_CREAT | os.O_RDWR
                open_mode = 0o644
            case 'secrets.tdb':
                tdb_flags = tdb.DEFAULT
                open_flags = os.O_RDWR
                open_mode = 0o600
            case 'group_mapping.tdb' | 'group_mapping_rejects.tdb' | 'passdb.tdb':
                tdb_flags = tdb.DEFAULT
                open_flags = os.O_CREAT | os.O_RDWR
                open_mode = 0o600
            case _:
                tdb_flags = tdb.DEFAULT
                open_flags = os.O_CREAT | os.O_RDWR
                open_mode = 0o600

        self.keys_null_terminated = keys_are_null_terminated(name, self.data_type)

        match self.path_type:
            case TDBPathType.CUSTOM:
                if not os.path.isabs(name):
                    raise ValueError(
                        f'{name}: must be an absolute path when using custom TDB path'
                    )
                self.full_path = name
            case _:
                if not os.path.exists(self.path_type.value):
                    os.makedirs(self.path_type.value, mode=0o700, exist_ok=True)

                self.full_path = f'{self.path_type.value}/{name}.tdb'

        self.hdl = tdb.Tdb(self.full_path, 0, tdb_flags, open_flags, open_mode)
        self.options = options


@contextmanager
def get_tdb_handle(name: str, tdb_options: TDBOptions) -> Generator[TDBHandle]:
    """ Open handle on TDB file under a threading lock """
    lock = TDB_LOCKS[name]
    with lock:
        if (entry := TDB_HANDLES.get(name)) is None:
            entry = TDB_HANDLES.setdefault(name, TDBHandle(name, tdb_options))

        if entry.options != tdb_options:
            raise ValueError('Inconsistent options')

        if not entry.validate_handle():
            entry.close()
            entry = TDBHandle(name, tdb_options)
            TDB_HANDLES[name] = entry

        yield entry


def close_sysdataset_tdb_handles() -> None:
    """
    Some samba / winbind-related TDB files are located in system dataset
    This method provides machanism to close them when moving system dataset path
    """
    for tdb_file in list(TDB_HANDLES.keys()):
        if not tdb_file.startswith(SYSDATASET_PATH):
            continue

        with TDB_LOCKS[tdb_file]:
            entry = TDB_HANDLES[tdb_file]
            entry.close()
