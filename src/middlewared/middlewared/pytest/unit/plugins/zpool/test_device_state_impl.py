from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from middlewared.plugins.zpool.device_state_impl import find_disk_vdev, offline_impl, online_impl
from middlewared.plugins.zpool.exceptions import (
    ZpoolVdevIsCacheException,
    ZpoolVdevIsSpareException,
    ZpoolVdevNotDiskException,
    ZpoolVdevNotFoundException,
)


def vdev(guid, vdev_type="disk", children=None):
    return SimpleNamespace(guid=guid, vdev_type=vdev_type, children=tuple(children) if children else None)


def make_pool():
    # mirror-0 has spare 300 swapped in for disk 201; spare 301 and dRAID spare 302 are available
    status = SimpleNamespace(
        storage_vdevs=(
            vdev(
                100,
                "mirror",
                [
                    vdev(200),
                    vdev(110, "spare", [vdev(201), vdev(300)]),
                ],
            ),
            vdev(120, "draid1:1d:3c:1s", [vdev(210), vdev(211), vdev(212)]),
        ),
        support_vdevs=SimpleNamespace(
            cache=(vdev(220),),
            log=(vdev(130, "mirror", [vdev(230), vdev(231)]),),
            special=(),
            dedup=(),
        ),
        spares=(vdev(300), vdev(301), vdev(302, "dspare")),
    )
    zpool = Mock()
    zpool.name = "tank"
    zpool.status.return_value = status
    return zpool


@pytest.mark.parametrize("guid", ["200", "201", "210", "220", "231"])
def test_finds_disks_in_every_vdev_class(guid):
    assert find_disk_vdev(make_pool(), guid).guid == int(guid)


def test_finds_a_spare_in_use_where_it_replaces_a_disk():
    zpool = make_pool()
    found = find_disk_vdev(zpool, "300")
    assert found is zpool.status.return_value.storage_vdevs[0].children[1].children[1]


@pytest.mark.parametrize(
    "guid,vdev_type", [("100", "mirror"), ("110", "spare"), ("120", "draid1:1d:3c:1s"), ("130", "mirror")]
)
def test_refuses_interior_vdevs(guid, vdev_type):
    with pytest.raises(ZpoolVdevNotDiskException) as e:
        find_disk_vdev(make_pool(), guid)
    assert str(e.value) == f"'tank': vdev {guid} is a {vdev_type} vdev, not a disk"


@pytest.mark.parametrize("guid", ["301", "302"])
def test_refuses_spares_not_in_use(guid):
    with pytest.raises(ZpoolVdevIsSpareException):
        find_disk_vdev(make_pool(), guid)


@pytest.mark.parametrize("guid", ["999", "0x c8", "0200", ""])
def test_refuses_guids_not_in_the_pool(guid):
    with pytest.raises(ZpoolVdevNotFoundException):
        find_disk_vdev(make_pool(), guid)


@pytest.mark.parametrize("impl,method", [(offline_impl, "offline_device"), (online_impl, "online_device")])
def test_impl_hands_the_binding_the_decimal_guid(impl, method):
    zpool = make_pool()
    lzh = Mock()
    lzh.open_pool.return_value = zpool
    impl(lzh, "tank", "231")
    lzh.open_pool.assert_called_once_with(name="tank")
    getattr(zpool, method).assert_called_once_with(device="231")


@pytest.mark.parametrize("impl,method", [(offline_impl, "offline_device"), (online_impl, "online_device")])
def test_impl_does_not_call_the_binding_for_an_interior_vdev(impl, method):
    zpool = make_pool()
    lzh = Mock()
    lzh.open_pool.return_value = zpool
    with pytest.raises(ZpoolVdevNotDiskException):
        impl(lzh, "tank", "130")
    getattr(zpool, method).assert_not_called()


def test_offline_refuses_a_cache_disk():
    zpool = make_pool()
    lzh = Mock()
    lzh.open_pool.return_value = zpool
    with pytest.raises(ZpoolVdevIsCacheException):
        offline_impl(lzh, "tank", "220")
    zpool.offline_device.assert_not_called()


def test_online_accepts_a_cache_disk():
    zpool = make_pool()
    lzh = Mock()
    lzh.open_pool.return_value = zpool
    online_impl(lzh, "tank", "220")
    zpool.online_device.assert_called_once_with(device="220")
