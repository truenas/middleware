import contextlib
import time

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


def assert_has_outdated_pool_alert(pool_name, has):
    for i in range(60):
        alerts = call("alert.list")
        if any((i["klass"] == "PoolUpgraded" and i["args"] == pool_name for i in alerts)) == has:
            break

        time.sleep(1)
    else:
        assert False, alerts


@contextlib.contextmanager
def outdated_pool():
    with another_pool() as pool:
        device = pool["topology"]["data"][0]["path"]
        ssh(f"zpool export {pool['name']}")
        ssh(f"zpool create test -o altroot=/mnt -o feature@sha512=disabled -f {device}")
        assert_has_outdated_pool_alert(pool["name"], True)
        yield pool


def test_outdated_pool_alert_removed_on_pool_upgrade():
    with outdated_pool() as pool:
        call("pool.upgrade", pool["id"])

        assert_has_outdated_pool_alert(pool["name"], False)


def test_outdated_pool_alert_removed_on_pool_delete():
    with outdated_pool() as pool:
        pass

    assert_has_outdated_pool_alert(pool["name"], False)
