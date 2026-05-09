"""NFSv4.2 OP_COPY (RFC 7862 §15.2) protocol tests.

Synchronous OP_COPY only.  Async OP_COPY can't be reliably tested
in our CI framework: knfsd's async-offload cleanup is tied to a
laundromat tick, which races dataset teardown.  The helper API
(``copy(synchronous=False)``, ``offload_status()``,
``offload_cancel()``, ``on_cb_offload``) is in ``pynfs_proto.py``
for use outside CI.

OP_CLONE coverage lives in ``test_nfs_server_side_copy.py``.
"""

import secrets

from middlewared.test.integration.utils import call, pool, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share
from protocols.pynfs_proto import PynfsClient
import pytest
from xdrdef.nfs4_const import NFS4_OK

NFS_SHARE_OPTS = {"mapall_user": "root", "mapall_group": "root"}

# Sync COPY payload — well under the kernel's 4 MiB single-iteration
# cap, so a single sync call returns the full count.
SYNC_PAYLOAD_SIZE = 1 << 20  # 1 MiB


def _bcloneused():
    res = call(
        "zpool.query_impl",
        {"pool_names": [pool], "properties": ["bcloneused"]},
    )
    return int(res[0]["properties"]["bcloneused"]["value"])


def _sync_pool():
    ssh(f"zpool sync {pool}")


# ---------------------------------------------------------------------------
# Synchronous OP_COPY
# ---------------------------------------------------------------------------


@pytest.mark.timeout(300)
def test_copy_sync_full_file_data_matches(start_nfs, nfs_dataset):
    """Synchronous OP_COPY with ``ca_count=size`` writes the full
    source contents to dst byte-for-byte and reports
    ``wr_count == size`` plus ``cr_synchronous==True``."""
    payload = secrets.token_bytes(SYNC_PAYLOAD_SIZE)
    with nfs_dataset("nfs_copy_full") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                n.create("src")
                n.write("src", payload)
                n.create("dst")
                res = n.copy("src", "dst", count=SYNC_PAYLOAD_SIZE)
                assert res.status == NFS4_OK
                assert res.bytes_written == SYNC_PAYLOAD_SIZE
                assert res.synchronous is True
                assert res.cb_stateid is None
                assert n.read("dst") == payload


@pytest.mark.timeout(300)
def test_copy_sync_count_zero_copies_to_eof(start_nfs, nfs_dataset):
    """RFC 7862 §15.2: ``ca_count == 0`` means copy from
    ``ca_src_offset`` through end-of-file."""
    payload = secrets.token_bytes(SYNC_PAYLOAD_SIZE)
    with nfs_dataset("nfs_copy_eof") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                n.create("src")
                n.write("src", payload)
                n.create("dst")
                res = n.copy("src", "dst", count=0)
                assert res.bytes_written == SYNC_PAYLOAD_SIZE
                assert n.read("dst") == payload


# Default ZFS recordsize.  Sub-range OP_COPY paths through
# zfs_clone_range require recordsize-aligned offsets and counts; non-
# aligned partial copies fall back to splice and don't move
# ``bcloneused``.  Use this for the partial-range and bcloneused tests.
RECORDSIZE = 128 * 1024


@pytest.mark.timeout(300)
def test_copy_sync_partial_range_preserves_surroundings(start_nfs, nfs_dataset):
    """OP_COPY of a sub-range copies only that range; bytes on dst
    outside the copy window keep their pre-existing contents.
    Offsets and count are recordsize-aligned so the BRT path is
    eligible (the surroundings check passes regardless of which
    code path the kernel picks)."""
    src_a = bytes([0x11]) * RECORDSIZE
    src_b = bytes([0x22]) * RECORDSIZE  # the slice we copy
    src_c = bytes([0x33]) * RECORDSIZE
    src_d = bytes([0x44]) * RECORDSIZE
    src_payload = src_a + src_b + src_c + src_d

    dst_pre = bytes([0x55]) * (4 * RECORDSIZE)

    with nfs_dataset("nfs_copy_partial") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                n.create("src")
                n.write("src", src_payload)
                n.create("dst")
                n.write("dst", dst_pre)
                res = n.copy(
                    "src",
                    "dst",
                    src_offset=RECORDSIZE,
                    dst_offset=RECORDSIZE,
                    count=RECORDSIZE,
                )
                assert res.bytes_written == RECORDSIZE
                got = n.read("dst")

    expected = dst_pre[:RECORDSIZE] + src_b + dst_pre[2 * RECORDSIZE :]
    assert got == expected


@pytest.mark.timeout(300)
def test_copy_sync_increments_bcloneused(start_nfs, nfs_dataset):
    """Sync OP_COPY of a multi-record random payload goes through
    ZFS's ``zfs_copy_file_range``, which uses the BRT under the
    hood, so ``bcloneused`` rises after the operation commits."""
    payload = secrets.token_bytes(SYNC_PAYLOAD_SIZE)
    with nfs_dataset("nfs_copy_bcl") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                n.create("src")
                n.write("src", payload)
                n.create("dst")

                _sync_pool()
                before = _bcloneused()

                res = n.copy("src", "dst", count=SYNC_PAYLOAD_SIZE)
                assert res.bytes_written == SYNC_PAYLOAD_SIZE

                _sync_pool()
                after = _bcloneused()

            assert after > before, f"bcloneused did not increase after sync OP_COPY: before={before} after={after}"


@pytest.mark.timeout(300)
def test_copy_sync_cross_dataset_same_pool(start_nfs, nfs_dataset):
    """Sync OP_COPY between two datasets in the same pool: both
    files share the same ``copy_file_range`` file-op (ZFS's
    ``zpl_copy_file_range``), and ``vfs_copy_file_range`` only
    requires the *same* copy_file_range function pointer - not the
    same superblock - to dispatch into the FS hook directly.  ZFS's
    hook tries ``zfs_clone_range`` first and only falls back to a
    splice copy on EXDEV/EOPNOTSUPP/EAGAIN/EINVAL, so cross-dataset
    same-pool with matching properties hits the BRT clone path and
    ``bcloneused`` rises after the operation commits."""
    payload = secrets.token_bytes(SYNC_PAYLOAD_SIZE)
    with nfs_dataset("nfs_copy_xds_a") as ds_a, nfs_dataset("nfs_copy_xds_b") as ds_b:
        path_a = f"/mnt/{ds_a}"
        path_b = f"/mnt/{ds_b}"
        with nfs_share(path_a, NFS_SHARE_OPTS), nfs_share(path_b, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, export_path=None, vers=4.2) as n:
                src = f"{path_a}/src"
                dst = f"{path_b}/dst"
                n.create(src)
                n.write(src, payload)
                n.create(dst)

                _sync_pool()
                before = _bcloneused()

                res = n.copy(src, dst, count=SYNC_PAYLOAD_SIZE)
                assert res.bytes_written == SYNC_PAYLOAD_SIZE

                _sync_pool()
                after = _bcloneused()

                assert n.read(dst) == payload

            assert after > before, (
                f"cross-dataset sync OP_COPY did not increase "
                f"bcloneused: before={before} after={after}"
            )


