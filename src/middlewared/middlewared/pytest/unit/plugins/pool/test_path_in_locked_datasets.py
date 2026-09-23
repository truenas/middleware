from unittest.mock import Mock

import pytest

from middlewared.plugins.pool_.dataset_encryption_info import PoolDatasetService

SNAPSHOT_PATHS = ["/dev/zvol/tank/vol@snap", "/mnt/tank/vol@snap", "tank/vol@snap"]


def make_tls(key_is_loaded):
    def open_resource(*, name):
        if "@" in name:
            return Mock(spec=[])
        resource = Mock()
        resource.crypto.return_value.info.return_value.key_is_loaded = key_is_loaded
        return resource

    tls = Mock()
    tls.lzh.open_resource.side_effect = open_resource
    return tls


def make_middleware():
    middleware = Mock()
    middleware.call_sync.side_effect = KeyError("about_to_lock_dataset")
    return middleware


def opened_names(tls):
    return [call.kwargs["name"] for call in tls.lzh.open_resource.call_args_list]


@pytest.mark.parametrize("path", SNAPSHOT_PATHS)
def test_snapshot_of_a_locked_dataset_is_locked(path):
    tls = make_tls(key_is_loaded=False)

    assert PoolDatasetService(make_middleware()).path_in_locked_datasets(tls, path) is True
    names = opened_names(tls)
    assert all("@" not in name for name in names)
    assert "tank/vol" in names


@pytest.mark.parametrize("path", SNAPSHOT_PATHS)
def test_snapshot_of_an_unlocked_dataset_is_not_locked(path):
    tls = make_tls(key_is_loaded=True)

    assert PoolDatasetService(make_middleware()).path_in_locked_datasets(tls, path) is False
    names = opened_names(tls)
    assert all("@" not in name for name in names)
    assert "tank/vol" in names


@pytest.mark.parametrize("path", SNAPSHOT_PATHS)
def test_snapshot_of_a_dataset_about_to_lock_is_locked(path):
    middleware = Mock()
    middleware.call_sync.return_value = "tank/vol"
    tls = make_tls(key_is_loaded=True)

    assert PoolDatasetService(middleware).path_in_locked_datasets(tls, path) is True
    tls.lzh.open_resource.assert_not_called()
