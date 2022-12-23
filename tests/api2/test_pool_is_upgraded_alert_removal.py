import contextlib

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


@contextlib.contextmanager
def outdated_pool():
    with another_pool() as pool:
        device = pool["topology"]["data"][0]["path"]
        ssh(f"zpool export {pool['name']}")
        ssh(f"zpool create test -o altroot=/mnt -o feature@sha512=disabled -f {device}")
        yield pool


def test_outdated_pool_alert_removed_on_pool_upgrade():
    with outdated_pool() as pool:
        call("pool.upgrade", pool["id"])

        alerts = call("alert.list")
        assert not any((i["klass"] == "PoolUpgraded" and i["args"] == pool["name"] for i in alerts)), alerts


def test_outdated_pool_alert_removed_on_pool_delete():
    with outdated_pool() as pool:
        pass

    alerts = call("alert.list")
    assert not any((i["klass"] == "PoolUpgraded" and i["args"] == pool["name"] for i in alerts)), alerts
