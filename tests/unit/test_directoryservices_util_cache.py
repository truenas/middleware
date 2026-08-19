"""
Unit tests for the directory services cache helpers in
`middlewared.plugins.directoryservices_.util_cache`.

These cover the storage-level behaviour that is otherwise only exercised against a live
AD / IPA / LDAP domain: the id/name key schema, temporary-file handling during a cache
fill, and the version / expiration bookkeeping.
"""

import os

import pytest

from middlewared.plugins.directoryservices_ import util_cache
from middlewared.plugins.directoryservices_.util_cache import (
    CACHE_LIFETIME,
    DSCacheFile,
    DSCacheFill,
    _tdb_add_expiration,
    _tdb_add_version,
    check_cache_expired,
    check_cache_version,
    expire_cache,
    insert_cache_entry,
    query_cache_entries,
    retrieve_cache_entry,
)
from middlewared.plugins.idmap_.idmap_constants import IDType
from middlewared.service_exception import MatchNotFound
from middlewared.utils.tdb import TDB_HANDLES
from middlewared.utils.time_utils import utc_now

TEST_VERSION = "27.0.0-TEST"


def user_entry(uid: int, username: str) -> dict:
    return {
        "id": 100000000 + uid,
        "uid": uid,
        "username": username,
        "home": f"/home/{username}",
        "shell": "/usr/bin/sh",
        "full_name": username,
        "local": False,
        "smb": True,
        "sid": f"S-1-5-21-1-2-3-{uid}",
        "roles": [],
    }


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """Point the cache helpers at a temporary directory.

    `DSCacheFile.path` reads the module-level CACHE_DIR at call time, so patching the
    module attribute is sufficient. TDB handles are cached process-wide by path, so drop
    any handle this test opened to keep tests independent.
    """
    monkeypatch.setattr(util_cache, "CACHE_DIR", str(tmp_path))
    yield tmp_path

    for path in [p for p in TDB_HANDLES if p.startswith(str(tmp_path))]:
        try:
            TDB_HANDLES.pop(path).close()
        except Exception:
            pass


def build_cache(entries=None, version=TEST_VERSION, expiration=None):
    """Produce a committed pair of cache files, optionally seeded with user entries."""
    if expiration is None:
        expiration = utc_now(naive=False) + CACHE_LIFETIME

    with DSCacheFill() as dc:
        for hdl in (dc.users_handle, dc.groups_handle):
            _tdb_add_version(hdl, version)
            _tdb_add_expiration(hdl, expiration)

        for entry in entries or []:
            util_cache._tdb_add_entry(dc.users_handle, entry["uid"], entry["username"], entry)

        dc._commit()


def temp_files(cache_dir) -> list:
    return sorted(p.name for p in cache_dir.glob("directory_service_cache_tmp_*"))


def test__insert_cache_entry_is_retrievable_by_id_and_name(cache_dir):
    """Lazy insertion must write both the ID_ and NAME_ keys.

    Regression test: the NAME_ key was previously built from the numeric id, so a lazily
    inserted entry could never be found by name and every by-name lookup fell through to
    a fresh NSS + idmap round-trip.
    """
    entry = user_entry(10001, "TESTDOM\\jdoe")
    insert_cache_entry(IDType.USER, entry["uid"], entry["username"], entry)

    assert retrieve_cache_entry(IDType.USER, None, entry["uid"]) == entry
    assert retrieve_cache_entry(IDType.USER, entry["username"], None) == entry


def test__retrieve_cache_entry_miss_raises(cache_dir):
    insert_cache_entry(IDType.USER, 10001, "TESTDOM\\jdoe", user_entry(10001, "TESTDOM\\jdoe"))

    with pytest.raises(MatchNotFound):
        retrieve_cache_entry(IDType.USER, "TESTDOM\\nobody", None)

    with pytest.raises(MatchNotFound):
        retrieve_cache_entry(IDType.USER, None, 99999)


def test__query_cache_entries_returns_id_keyed_entries_once(cache_dir):
    """Query walks ID_-prefixed keys only, so each entry appears exactly once even
    though it is stored under both an ID_ and a NAME_ key."""
    entries = [user_entry(10001 + i, f"TESTDOM\\user{i}") for i in range(3)]
    build_cache(entries)

    found = query_cache_entries(IDType.USER, [], {})

    assert sorted(e["uid"] for e in found) == [10001, 10002, 10003]
    assert len(found) == len(entries)


def test__dscachefill_commit_leaves_no_temp_files(cache_dir):
    build_cache()

    assert temp_files(cache_dir) == []
    assert os.path.exists(DSCacheFile.USER.path)
    assert os.path.exists(DSCacheFile.GROUP.path)


def test__dscachefill_failure_removes_temp_files(cache_dir):
    """A fill that raises before _commit() must not strand its temporary files.

    NssError / WBCErr / job abort are all documented as expected failures for
    fill_cache, so this is the common path rather than an edge case.
    """
    with pytest.raises(RuntimeError, match="fill failed"):
        with DSCacheFill():
            assert temp_files(cache_dir) != []
            raise RuntimeError("fill failed")

    assert temp_files(cache_dir) == []
    # a failed fill must leave the live cache untouched
    assert not os.path.exists(DSCacheFile.USER.path)


def test__dscachefill_failure_preserves_previous_cache(cache_dir):
    build_cache([user_entry(10001, "TESTDOM\\jdoe")])

    with pytest.raises(RuntimeError):
        with DSCacheFill():
            raise RuntimeError("fill failed")

    assert temp_files(cache_dir) == []
    assert query_cache_entries(IDType.USER, [], {})[0]["uid"] == 10001


def test__check_cache_version_keeps_matching_cache(cache_dir):
    build_cache()

    check_cache_version(TEST_VERSION)

    assert os.path.exists(DSCacheFile.USER.path)
    assert os.path.exists(DSCacheFile.GROUP.path)


def test__check_cache_version_removes_mismatched_cache(cache_dir):
    build_cache(version="26.04.0")

    check_cache_version(TEST_VERSION)

    assert not os.path.exists(DSCacheFile.USER.path)
    assert not os.path.exists(DSCacheFile.GROUP.path)


def test__check_cache_expired_false_for_fresh_cache(cache_dir):
    build_cache()

    assert check_cache_expired() is False


def test__check_cache_expired_true_for_missing_cache(cache_dir):
    assert check_cache_expired() is True


def test__expire_cache_marks_cache_expired(cache_dir):
    """expire_cache must write a timestamp that check_cache_expired reads as expired.

    Both sides deal in timezone-aware UTC; this pins that they stay consistent rather
    than relying on ejson attaching UTC when the value is read back.
    """
    build_cache()
    assert check_cache_expired() is False

    expire_cache()

    assert check_cache_expired() is True
