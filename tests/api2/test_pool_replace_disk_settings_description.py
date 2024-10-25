import pytest

from middlewared.test.integration.assets.pool import _2_disk_mirror_topology, another_pool
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def pool():
    with another_pool(topology=_2_disk_mirror_topology) as pool:
        yield pool


@pytest.mark.parametrize("preserve_description", [True, False])
def test_pool_replace_disk(pool, preserve_description):
    pool = call("pool.get_instance", pool["id"])
    flat_top = call("pool.flatten_topology", pool["topology"])
    pool_top = [vdev for vdev in flat_top if vdev["type"] == "DISK"]

    to_replace_vdev = pool_top[0]
    to_replace_disk = call("disk.query", [["name", "=", to_replace_vdev["disk"]]], {"get": True})
    new_disk = call("disk.get_unused")[0]

    call("disk.update", to_replace_disk["identifier"], {"description": "Preserved disk description"})
    call("disk.update", new_disk["identifier"], {"description": "Unchanged disk description"})

    call("pool.replace", pool["id"], {
        "label": to_replace_vdev["guid"],
        "disk": new_disk["identifier"],
        "force": True,
        "preserve_description": preserve_description,
    }, job=True)

    new_disk = call("disk.get_instance", new_disk["identifier"])
    if preserve_description:
        assert new_disk["description"] == "Preserved disk description"
    else:
        assert new_disk["description"] == "Unchanged disk description"
