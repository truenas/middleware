import os

from auto_config import pool_name
from middlewared.test.integration.assets.zfs_resource import zfs_resource
from middlewared.test.integration.utils import call

PASSPHRASE = "passphrase123"


def test_zfs_resource_encryption_lock_unlock():
    path = os.path.join(pool_name, "test_zr_encryption_lock_unlock")
    with zfs_resource(path, {"encryption": {"passphrase": PASSPHRASE}}):
        keys = [{"path": path, "passphrase": PASSPHRASE}]
        call("zfs.resource.encryption.lock", {"path": path}, job=True)

        summary = call("zfs.resource.encryption.unlock_summary", {"path": path, "keys": keys}, job=True)
        for entry in summary:
            if entry["path"] == path:
                break
        else:
            raise AssertionError(summary)
        assert entry["valid_key"] is True, entry
        assert entry["locked"] is True, entry
        assert entry["key_format"] == "passphrase", entry

        result = call("zfs.resource.encryption.unlock", {"path": path, "keys": keys}, job=True)
        assert path in result["unlocked"], result
