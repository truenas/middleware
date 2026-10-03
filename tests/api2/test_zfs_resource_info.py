import errno

import pytest

from middlewared.service_exception import ValidationError
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


def test_recommended_zvol_blocksize_nonexistent_pool():
    with pytest.raises(ValidationError) as ve:
        call("zfs.resource.recommended_zvol_blocksize", "nonexistent_pool")

    assert ve.value.attribute == "zfs.resource.recommended_zvol_blocksize.pool"
    assert ve.value.errmsg == "'nonexistent_pool' does not exist"
    assert ve.value.errno == errno.ENOENT


def test_zfs_resource_processes_holder_is_reported():
    """A process holding a file on the dataset open is reported with its pid."""
    with dataset("test_processes_held") as ds:
        ssh(f"touch /mnt/{ds}/holdme")
        pid = int(ssh(f"( tail -f /mnt/{ds}/holdme >/dev/null 2>&1 & echo $! )").strip())
        try:
            assert pid in [p["pid"] for p in call("zfs.resource.processes", ds)]
        finally:
            ssh(f"kill {pid}")
