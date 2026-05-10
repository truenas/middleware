"""NFSv4.2 server-side copy (OP_CLONE) protocol tests.

Drives create + write + clone sequences over NFSv4.2 directly via
pynfs and asserts both protocol-level behaviour and the underlying
ZFS BRT block-cloning effect (a copy that silently fell back to a
byte-for-byte transfer would still pass a protocol-only smoke check
but wouldn't move pool ``bcloneused``).

OP_COPY coverage lives in ``test_nfs_op_copy.py``.
"""

import secrets

from middlewared.test.integration.utils import call, pool, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import nfs_share
from protocols.pynfs_proto import PynfsClient
import pytest
from xdrdef.nfs4_const import NFS4ERR_INVAL, NFS4ERR_XDEV

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


def _sync_pool():
    ssh(f"zpool sync {pool}")


@pytest.mark.timeout(300)
def test_clone_full_file_increments_bcloneused(start_nfs, nfs_dataset):
    """Full NFSv4.2 OP_CLONE of a multi-record random payload bumps
    ``bcloneused`` - confirms the operation actually goes through the
    ZFS BRT and isn't being satisfied by a byte-for-byte fallback."""
    with nfs_dataset("nfs_clone_bcl") as ds:
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
                _sync_pool()
                before = _bcloneused()

                n.clone("src", "dst")

                # OP_CLONE updates the BRT in the txg in which the
                # request commits; force a sync so the counter we
                # read reflects the just-completed clone.
                _sync_pool()
                after = _bcloneused()

            assert after > before, (
                f"bcloneused did not increase after OP_CLONE: "
                f"before={before} after={after}"
            )


@pytest.mark.timeout(300)
def test_clone_full_file_data_matches(start_nfs, nfs_dataset):
    """OP_CLONE with count=0 (clone-to-EOF) produces a destination
    whose contents byte-for-byte match the source."""
    with nfs_dataset("nfs_clone_eq") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                payload = secrets.token_bytes(PAYLOAD_SIZE)
                n.create("src")
                n.write("src", payload)
                n.create("dst")
                n.clone("src", "dst")
                got = n.read("dst")
            assert got == payload


# Default ZFS recordsize.  ``zfs_clone_range`` rejects offsets and
# counts that aren't recordsize-aligned with EINVAL ("Offsets and len
# must be at block boundaries"), so partial-range clone tests must
# use multiples of this value.
RECORDSIZE = 128 * 1024


@pytest.mark.timeout(300)
def test_clone_partial_range_preserves_surroundings(start_nfs, nfs_dataset):
    """Cloning a sub-range copies only that range; bytes on dst
    outside the clone window keep their pre-existing contents.
    Offsets and count must be recordsize-aligned for ZFS BRT cloning."""
    src_a = bytes([0xAA]) * RECORDSIZE
    src_b = bytes([0xBB]) * RECORDSIZE  # the slice we clone
    src_c = bytes([0xCC]) * RECORDSIZE
    src_d = bytes([0xDD]) * RECORDSIZE
    src_payload = src_a + src_b + src_c + src_d

    dst_pre = bytes([0xEE]) * (4 * RECORDSIZE)

    with nfs_dataset("nfs_clone_partial") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                n.create("src")
                n.write("src", src_payload)
                n.create("dst")
                n.write("dst", dst_pre)
                # Clone src[1*rs : 2*rs] -> dst[1*rs : 2*rs]
                n.clone(
                    "src",
                    "dst",
                    src_offset=RECORDSIZE,
                    dst_offset=RECORDSIZE,
                    count=RECORDSIZE,
                )
                got = n.read("dst")

    expected = (
        dst_pre[:RECORDSIZE]  # untouched head
        + src_b  # cloned region
        + dst_pre[2 * RECORDSIZE :]  # untouched tail
    )
    assert got == expected


@pytest.mark.timeout(300)
def test_clone_overlapping_same_file_fails(start_nfs, nfs_dataset):
    """OP_CLONE within a single file with overlapping source and
    destination ranges is rejected by ZFS (``zfs_clone_range``
    explicitly rejects overlap), surfacing as NFS4ERR_INVAL."""
    payload = secrets.token_bytes(4 * RECORDSIZE)
    with nfs_dataset("nfs_clone_overlap") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                n.create("f")
                n.write("f", payload)
                # Same file, ranges [1rs, 3rs) and [2rs, 4rs) overlap
                # in [2rs, 3rs).
                n.clone(
                    "f",
                    "f",
                    src_offset=RECORDSIZE,
                    dst_offset=2 * RECORDSIZE,
                    count=2 * RECORDSIZE,
                    expect_status=NFS4ERR_INVAL,
                )


@pytest.mark.timeout(300)
def test_clone_count_past_eof_fails(start_nfs, nfs_dataset):
    """OP_CLONE with ``cl_src_offset + cl_count > src_size`` returns
    NFS4ERR_INVAL.  ZFS rejects (or returns a partial count, which
    nfsd then surfaces as EINVAL because the wire-level requirement
    is full count - cloned bytes equality)."""
    src_size = 4096
    payload = secrets.token_bytes(src_size)
    with nfs_dataset("nfs_clone_eof") as ds:
        path = f"/mnt/{ds}"
        with nfs_share(path, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, path, vers=4.2) as n:
                n.create("src")
                n.write("src", payload)
                n.create("dst")
                # Ask to clone 8192 bytes from a 4096-byte source.
                n.clone(
                    "src",
                    "dst",
                    src_offset=0,
                    dst_offset=0,
                    count=8192,
                    expect_status=NFS4ERR_INVAL,
                )


@pytest.mark.timeout(300)
def test_clone_cross_dataset_returns_xdev(start_nfs, nfs_dataset):
    """Each ZFS dataset is its own kernel superblock.  The Linux
    VFS clone path (``vfs_clone_file_range``) enforces a same-
    superblock invariant before dispatching to the filesystem and
    returns ``-EXDEV`` if the source and destination differ, so nfsd
    surfaces ``NFS4ERR_XDEV`` for cross-dataset OP_CLONE - even when
    the datasets live in the same pool and ZFS's BRT could in
    principle clone between them.  Cross-dataset bulk transfer must
    use OP_COPY, whose dispatch path goes directly through ZFS's
    ``zpl_copy_file_range`` hook (which does support cross-dataset
    BRT cloning); see ``test_nfs_op_copy.py``.

    Both files are opened via one pynfs session in absolute-path
    mode so the pair of stateids can be used in a single CLONE
    compound."""
    with nfs_dataset("nfs_clone_xds_a") as ds_a, nfs_dataset("nfs_clone_xds_b") as ds_b:
        path_a = f"/mnt/{ds_a}"
        path_b = f"/mnt/{ds_b}"
        with nfs_share(path_a, NFS_SHARE_OPTS), nfs_share(path_b, NFS_SHARE_OPTS):
            with PynfsClient(truenas_server.ip, export_path=None, vers=4.2) as n:
                src = f"{path_a}/src"
                dst = f"{path_b}/dst"
                n.create(src)
                n.write(src, secrets.token_bytes(PAYLOAD_SIZE))
                n.create(dst)
                n.clone(src, dst, expect_status=NFS4ERR_XDEV)
