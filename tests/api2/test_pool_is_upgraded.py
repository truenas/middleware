import pytest

from middlewared.test.integration.assets.pool import another_pool, pool
from middlewared.test.integration.utils import call, ssh

from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.fixture(scope="module")
def outdated_pool():
    with another_pool() as pool:
        device = pool["topology"]["data"][0]["path"]
        ssh(f"zpool export {pool['name']}")
        ssh(f"zpool create test -o altroot=/mnt -o feature@sha512=disabled -f {device}")
        yield pool


def test_is_upgraded():
    pool_id = call("pool.query", [["name", "=", pool]])[0]["id"]
    assert call("pool.is_upgraded", pool_id)


def test_is_outdated(outdated_pool):
    assert call("pool.is_upgraded", outdated_pool["id"]) is False


def test_is_outdated_in_list(outdated_pool):
    pool = call("pool.query", [["id", "=", outdated_pool["id"]]], {"extra": {"is_upgraded": True}})[0]
    assert pool["is_upgraded"] is False


def test_is_outdated_alert(outdated_pool):
    alerts = call("alert.list")
    assert any((i["klass"] == "PoolUpgraded" and i["args"] == outdated_pool["name"] for i in alerts))
