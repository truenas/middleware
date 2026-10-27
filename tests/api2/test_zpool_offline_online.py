import pytest

from middlewared.service_exception import CallError, ValidationError
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def mirror_with_spare_and_cache():
    with another_pool(
        topology=(
            4,
            lambda disks: {
                "data": [{"type": "MIRROR", "disks": disks[0:2]}],
                "spares": disks[2:3],
                "cache": [{"type": "STRIPE", "disks": disks[3:4]}],
            },
        )
    ) as pool:
        yield pool


def vdev_state(pool_name, guid):
    topology = call("zpool.query", {"pool_names": [pool_name], "topology": True})[0]["topology"]
    vdevs = [vdev for root in topology.values() for vdev in root]
    while vdevs:
        vdev = vdevs.pop()
        if str(vdev["guid"]) == guid:
            return vdev["state"]
        vdevs.extend(vdev["children"])
    raise AssertionError(f"{guid} is not in {pool_name}")


def online(pool_name, guid):
    call("zpool.online", {"pool_name": pool_name, "vdev_guid": guid})


@pytest.mark.parametrize("namespace", ["zpool", "pool"])
def test_offline_then_online(mirror_with_spare_and_cache, namespace):
    pool = mirror_with_spare_and_cache
    guid = pool["topology"]["data"][0]["children"][0]["guid"]
    try:
        if namespace == "zpool":
            call("zpool.offline", {"pool_name": pool["name"], "vdev_guid": guid})
        else:
            call("pool.offline", pool["id"], {"label": guid})
        assert vdev_state(pool["name"], guid) == "OFFLINE"

        if namespace == "zpool":
            online(pool["name"], guid)
        else:
            call("pool.online", pool["id"], {"label": guid})
        assert vdev_state(pool["name"], guid) == "ONLINE"
    finally:
        online(pool["name"], guid)


def test_offline_refused_when_no_replica_would_be_left(mirror_with_spare_and_cache):
    pool = mirror_with_spare_and_cache
    first, second = [disk["guid"] for disk in pool["topology"]["data"][0]["children"]]
    call("zpool.offline", {"pool_name": pool["name"], "vdev_guid": first})
    try:
        with pytest.raises(CallError, match="no valid replicas"):
            call("zpool.offline", {"pool_name": pool["name"], "vdev_guid": second})
        assert vdev_state(pool["name"], second) == "ONLINE"
    finally:
        online(pool["name"], first)


@pytest.mark.parametrize("method", ["zpool.offline", "zpool.online"])
@pytest.mark.parametrize(
    "target,attribute,message",
    [
        pytest.param(
            lambda pool: (pool["name"], pool["topology"]["data"][0]["guid"]),
            "vdev_guid",
            "is a mirror vdev, not a disk",
            id="mirror",
        ),
        pytest.param(
            lambda pool: (pool["name"], pool["topology"]["spare"][0]["guid"]),
            "vdev_guid",
            "is a hot spare that is not in use",
            id="available-spare",
        ),
        pytest.param(lambda pool: (pool["name"], "1"), "vdev_guid", "no vdev with GUID 1", id="unknown-guid"),
        pytest.param(
            lambda pool: ("nonexistent", pool["topology"]["data"][0]["children"][0]["guid"]),
            "pool_name",
            "'nonexistent' not found",
            id="unknown-pool",
        ),
    ],
)
def test_refused(mirror_with_spare_and_cache, method, target, attribute, message):
    pool_name, guid = target(mirror_with_spare_and_cache)
    with pytest.raises(ValidationError) as ve:
        call(method, {"pool_name": pool_name, "vdev_guid": guid})
    assert ve.value.attribute == f"{method}.{attribute}"
    assert message in ve.value.errmsg


def test_offline_refuses_a_cache_disk(mirror_with_spare_and_cache):
    pool = mirror_with_spare_and_cache
    with pytest.raises(ValidationError) as ve:
        call("zpool.offline", {"pool_name": pool["name"], "vdev_guid": pool["topology"]["cache"][0]["guid"]})
    assert ve.value.attribute == "zpool.offline.vdev_guid"
    assert "is a cache device" in ve.value.errmsg
