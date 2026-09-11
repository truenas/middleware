import enum
import importlib
from unittest.mock import Mock, patch

import pytest

from middlewared.plugins.zpool.exceptions import ZpoolNotFoundException

# The package re-exports the query_impl function under the module's name.
query_impl = importlib.import_module("middlewared.plugins.zpool.query_impl")


class FakeZFSError(enum.IntEnum):
    EZFS_NOENT = 2009
    EZFS_IO = 2004


class FakeZFSException(RuntimeError):
    def __init__(self, code):
        super().__init__(code.name)
        self.code = code


@pytest.fixture
def fake_pylibzfs():
    with (
        patch.object(query_impl, "ZFSError", FakeZFSError),
        patch.object(query_impl, "ZFSException", FakeZFSException),
    ):
        yield


def make_lzh(pools):
    """Build a handle whose open_pool() returns the mapped value or raises it."""

    def open_pool(name):
        result = pools[name]
        if isinstance(result, Exception):
            raise result
        return result

    return Mock(open_pool=Mock(side_effect=open_pool))


def test_missing_pool_is_skipped(fake_pylibzfs):
    lzh = make_lzh({"gone": FakeZFSException(FakeZFSError.EZFS_NOENT), "tank": Mock()})
    with patch.object(query_impl, "_build_pool_dict", return_value={"name": "tank"}):
        assert query_impl.query_impl(lzh, {"pool_names": ["gone", "tank"]}) == [{"name": "tank"}]


def test_missing_pool_raises_when_requested(fake_pylibzfs):
    lzh = make_lzh({"gone": FakeZFSException(FakeZFSError.EZFS_NOENT)})
    with pytest.raises(ZpoolNotFoundException):
        query_impl.query_impl(lzh, {"pool_names": ["gone"], "raise_on_noent": True})


def test_open_pool_other_errors_propagate(fake_pylibzfs):
    lzh = make_lzh({"tank": FakeZFSException(FakeZFSError.EZFS_IO)})
    with pytest.raises(FakeZFSException):
        query_impl.query_impl(lzh, {"pool_names": ["tank"]})


def test_noent_during_status_collection_is_not_treated_as_missing_pool(fake_pylibzfs):
    lzh = make_lzh({"tank": Mock()})
    exc = FakeZFSException(FakeZFSError.EZFS_NOENT)
    with (
        patch.object(query_impl, "_build_pool_dict", side_effect=exc),
        pytest.raises(FakeZFSException) as excinfo,
    ):
        query_impl.query_impl(lzh, {"pool_names": ["tank"]})
    assert excinfo.value is exc
