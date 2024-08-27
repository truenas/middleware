import os

from base64 import b64encode
from dataclasses import dataclass
from struct import pack
from uuid import uuid4
from .tdb import (
    TDBDataType,
    TDBHandle,
    TDBOptions,
    TDBPathType,
)


PAM_TDB_DIR = '/var/run/pam_tdb'
PAM_TDB_FILE = os.path.join(PAM_TDB_DIR, 'pam_tdb.tdb')
PAM_TDB_DIR_MODE = 0o700
PAM_TDB_VERSION = 1
PAM_TDB_MAX_KEYS = 10  # Max number of keys per user. Also defined in pam_tdb.c

PAM_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)


@dataclass(frozen=True)
class UserApiKey:
    expiry: int
    dbid: int
    userhash: str


@dataclass(frozen=True)
class PamTdbEntry:
    keys: list[UserApiKey]
    username: str


def _setup_pam_tdb_dir() -> None:
    os.makedirs(PAM_TDB_DIR, mode=PAM_TDB_DIR_MODE, exist_ok=True)
    os.chmod(PAM_TDB_DIR, PAM_TDB_DIR_MODE)


def _pack_user_api_key(api_key: UserApiKey) -> bytes:
    """
    Convert UserApiKey object to bytes for TDB insertion.
    This is packed struct with expiry converted into signed 64 bit
    integer, the database id (32-bit unsigned), and the userhash (pascal string)
    """
    if not isinstance(api_key, UserApiKey):
        raise TypeError(f'{type(api_key)}: not a UserApiKey')

    userhash = api_key.userhash.encode() + b'\x00'
    return pack(f'<qI{len(userhash)}p', api_key.expiry, api_key.dbid, userhash)


def write_entry(hdl: TDBHandle, entry: PamTdbEntry) -> None:
    """
    Convert PamTdbEntry object into a packed struct and insert
    into tdb file.

    key: username
    value: uint32_t (version) + uint32_t (cnt of keys)
    """
    if not isinstance(entry, PamTdbEntry):
        raise TypeError(f'{type(entry)}: expected PamTdbEntry')

    key_cnt = len(entry.keys)
    if key_cnt > PAM_TDB_MAX_KEYS:
        raise ValueError(f'{key_cnt}: count of entries exceeds maximum')

    entry_bytes = pack('<II', PAM_TDB_VERSION, len(entry.keys))
    parsed_cnt = 0
    for key in entry.keys:
        entry_bytes += _pack_user_api_key(key)
        parsed_cnt += 1

    # since we've already packed struct with array length
    # we need to rigidly ensure we don't exceed it.
    assert parsed_cnt == key_cnt
    hdl.store(entry.username, b64encode(entry_bytes))


def flush_user_api_keys(pam_entries: list[PamTdbEntry]) -> None:
    """
    Write a PamTdbEntry object to the pam_tdb file for user
    authentication. This method first writes to temporary file
    and then renames over pam_tdb file to ensure flush is atomic
    and reduce risk of lock contention while under a transaction
    lock.

    raises:
        TypeError - not PamTdbEntry
        AssertionError - count of entries changed while generating
            tdb payload
        RuntimeError - TDB library error
    """
    _setup_pam_tdb_dir()

    if not isinstance(pam_entries, list):
        raise TypeError('Expected list of PamTdbEntry objects')

    tmp_path = os.path.join(PAM_TDB_DIR, f'tmp_{uuid4()}.tdb')

    with TDBHandle(tmp_path, PAM_TDB_OPTIONS) as hdl:
        hdl.keys_null_terminated = False

        try:
            for entry in pam_entries:
                write_entry(hdl, entry)
        except Exception:
            os.remove(tmp_path)
            raise

    os.rename(tmp_path, PAM_TDB_FILE)
