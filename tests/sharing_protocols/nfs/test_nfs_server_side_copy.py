"""NFSv4.2 server-side copy (OP_CLONE) protocol test.

Drives the full create + write + clone sequence over NFSv4.2 and
confirms that ZFS block cloning actually fires on the appliance - a
copy that silently fell back to a byte-for-byte transfer would still
pass a protocol-only smoke check but wouldn't move pool
``bcloneused``.
"""

import secrets

import pytest

from middlewared.test.integration.utils import call, pool, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share
from protocols.pynfs_proto import PynfsClient


# Shares are exported with maproot=root so the pynfs client's
# AUTH_SYS uid=0 isn't squashed.  See tests/api2/test_300_nfs.py
# ::test_share_maproot for the squash behavior we're avoiding.
NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}

# 1 MiB - large enough to span multiple ZFS records at the default
# 128 KiB recordsize, so block cloning has something to dedup.  A
# few-byte payload would clone successfully but wouldn't move
# ``bcloneused``.
PAYLOAD_SIZE = 1 << 20


def _bcloneused():
    """Return pool ``bcloneused`` (bytes) via the zpool query API."""
    res = call(
        "zpool.query_impl",
        {
            "pool_names": [pool],
            "properties": ["bcloneused"],
        },
    )
    return int(res[0]["properties"]["bcloneused"]["value"])


@pytest.mark.timeout(300)
def test_server_side_copy(start_nfs, nfs_dataset):
    """Full NFSv4.2 server-side copy (create + write + OP_CLONE)
    triggers ZFS block cloning, visible as an increase in pool
    ``bcloneused``."""
    with nfs_dataset("nfs_ssc") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                # Random bytes so ZFS doesn't elide the write via
                # zero-block / embedded-block detection, which would
                # leave nothing in the BRT to clone.
                payload = secrets.token_bytes(PAYLOAD_SIZE)
                n.create("src")
                n.write("src", payload)
                n.create("dst")

                # Sync first so the baseline isn't moving from prior
                # async writes elsewhere on the pool.
                ssh(f"zpool sync {pool}")
                before = _bcloneused()

                n.clone("src", "dst")

                # OP_CLONE updates the BRT in the txg in which the
                # request commits; force a sync so the counter we
                # read reflects the just-completed clone.
                ssh(f"zpool sync {pool}")
                after = _bcloneused()

            assert after > before, (
                f"bcloneused did not increase after OP_CLONE: "
                f"before={before} after={after}"
            )
