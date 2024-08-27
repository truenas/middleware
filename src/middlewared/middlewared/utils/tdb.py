import os
import tdb
import enum
import json

from base64 import b64encode, b64decode
from collections import defaultdict, namedtuple
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH
from middlewared.service_exception import MatchNotFound
from threading import RLock

FD_CLOSED = -1
# Robust mutex support was added to libtdb after py-tdb was written and flags
# weren't updated. See lib/tdb/include/tdb.h
MUTEX_LOCKING = 4096

TDB_LOCKS = defaultdict(RLock)
TDBOptions = namedtuple('TdbFileOptions', ['backend', 'data_type'])
TDB_HANDLES = {}


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

    BYTES - binary data. API consumer submits as b64encoded string that is decoded before insertion.
    This is particularly relevant when interacting with TDB files used by 3rd party applications.

    JSON - submit as python dictionary and converted into JSON before insertion

    STRING - submit as python string and inserted as-is
    """
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
    value: str | dict = None


class TDBHandle:
    hdl = None
    name = None
    data_type = None
    path_type = None
    full_path = None
    opath_fd = FD_CLOSED
    keys_null_terminated = False

    def __enter__(self):
        return self

    def __exit__(self, tp, val, traceback):
        self.close()

    def close(self):
        """ Close the TDB handle and O_PATH open for the file """
        if self.opath_fd == FD_CLOSED and self.hdl is None:
            return

        if self.hdl is not None:
            self.hdl.close()
            self.hdl = None

        if self.opath_fd != FD_CLOSED:
            os.close(self.opath_fd)
            self.opath_fd = FD_CLOSED

    def validate_handle(self) -> bool:
        """
        Check whether the TDB handle is still valid
        If it is invalid, then a new handle object should be created.
        """
        if self.opath_fd == FD_CLOSED:
            return False

        if not os.path.exists(f'/proc/self/fd/{self.opath_fd}'):
            return False

        # if file has been renamed or deleted from under us, readlink will show different path
        return os.readlink(f'/proc/self/fd/{self.opath_fd}') == self.full_path

    def get(self, key: str) -> dict | str:
        """
        Retrieve the specified key

        Returns:
            dict if TDBDatatype is JSON
            str if TDBDatatype is BYTES or STRING

        Raises:
            MatchNotFound
            RuntimeError
        """
        tdb_key = key.encode()
        if self.keys_null_terminated:
            tdb_key += b"\x00"

        if (tdb_val := self.hdl.get(tdb_key)) is None:
            raise MatchNotFound(key)

        match self.data_type:
            case TDBDataType.BYTES:
                out = b64encode(tdb_val).decode()
            case TDBDataType.JSON:
                out = json.loads(tdb_val.decode())
            case TDBDataType.STRING:
                out = tdb_val.decode()
            case _:
                raise ValueError(f'{self.data_type}: unknown data type')

        return out

    def store(self, key: str, value: str | dict) -> None:
        """
        Set the specified `key` to the specified `value`.

        Raises:
            RuntimeError
            ValueError
        """
        tdb_key = key.encode()
        if self.keys_null_terminated:
            tdb_key += b'\x00'

        match self.data_type:
            case TDBDataType.BYTES:
                tdb_val = b64decode(value)
            case TDBDataType.JSON:
                tdb_val = json.dumps(value).encode()
            case TDBDataType.STRING:
                tdb_val = value.encode()
            case _:
                raise ValueError(f'{self.data_type}: unknown data type')

        self.hdl.store(tdb_key, tdb_val)

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

    def entries(self, include_keys: bool = True, key_prefix: str = None) -> Iterable[dict]:
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

    def batch_op(self, ops: list[TDBBatchOperation]) -> dict:
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
                self.keys_null_terminated = True
                open_flags = os.O_CREAT | os.O_RDWR
                open_mode = 0o644
            case 'secrets.tdb':
                tdb_flags = tdb.DEFAULT
                open_flags = os.O_RDWR
                open_mode = 0o600
            case 'group_mapping.tdb' | 'group_mapping_rejects.tdb' | 'passdb.tdb':
                tdb_flags = tdb.DEFAULT
                open_flags = os.O_RDWR
                self.keys_null_terminated = True
                open_flags = os.O_CREAT | os.O_RDWR
                open_mode = 0o600
            case _:
                tdb_flags = tdb.DEFAULT
                # Typically tdb files will have NULL-terminated keys
                self.keys_null_terminated = options.data_type is TDBDataType.BYTES
                open_flags = os.O_CREAT | os.O_RDWR
                open_mode = 0o600

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
        self.opath_fd = os.open(self.full_path, os.O_PATH)
        self.options = options


@contextmanager
def get_tdb_handle(name, tdb_options: TDBOptions):
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


def close_sysdataset_tdb_handles():
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
