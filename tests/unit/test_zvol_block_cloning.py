import os
import subprocess

import pytest
import truenas_pylibzfs
from truenas_api_client import Client


_1GiB = 1073741824
_1MiB = 1048576
_VOLBLOCKSIZE = '16K'
_EXPECTED_SHARED_BLOCKS = _1MiB // (16 * 1024)


@pytest.fixture(scope='module')
def zvols():
    """Two thin zvols (volblocksize=16K) under the dataset backing /var.

    Yields (src_name, dst_name, pool) where pool is a ZFSPool handle
    used by the test to sync after writes/clones.
    """
    with Client() as c:
        mnt = c.call(
            'filesystem.mount_info',
            [['mountpoint', '=', '/var']], {'get': True},
        )

    lz = truenas_pylibzfs.open_handle()
    src_name = f'{mnt["mount_source"]}/bclone_src'
    dst_name = f'{mnt["mount_source"]}/bclone_dst'
    pool = lz.open_pool(name=mnt['mount_source'].split('/')[0])
    for name in (src_name, dst_name):
        lz.create_resource(
            name=name,
            type=truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME,
            properties={
                truenas_pylibzfs.ZFSProperty.VOLSIZE: _1GiB,
                truenas_pylibzfs.ZFSProperty.VOLBLOCKSIZE: _VOLBLOCKSIZE,
                truenas_pylibzfs.ZFSProperty.REFRESERVATION: 'none',
            },
        )
    try:
        yield src_name, dst_name, pool
    finally:
        for name in (dst_name, src_name):
            lz.destroy_resource(name=name)


def _shared_l0_count(src_name, dst_name):
    """Count L0 data blocks shared between two zvols (per zdb)."""
    def dvas(name):
        out = subprocess.run(
            ['zdb', '-vvvvv', name],
            capture_output=True, text=True, check=True,
        ).stdout
        return {
            line.split()[2]
            for line in out.splitlines()
            if ' L0 ' in line and 'DVA' in line and 'dnode' not in line
        }
    return len(dvas(src_name) & dvas(dst_name))


def test_zvol_block_cloning(zvols):
    """
    Verify zvol-to-zvol copy_file_range produces shared L0 blocks
    (block cloning) rather than an independent copy. Identical L0
    DVA+checksum entries between src and dst in zdb output prove the
    destination references the source's blocks.
    """
    src_name, dst_name, pool = zvols
    src_path = f'/dev/zvol/{src_name}'
    dst_path = f'/dev/zvol/{dst_name}'

    with open(src_path, 'wb') as f:
        f.write(os.urandom(_1MiB))
    pool.sync_pool()

    fi = os.open(src_path, os.O_RDONLY | os.O_DIRECT)
    fo = os.open(dst_path, os.O_WRONLY | os.O_DIRECT)
    try:
        assert os.copy_file_range(fi, fo, _1MiB, 0, 0) == _1MiB
    finally:
        os.close(fi)
        os.close(fo)
    pool.sync_pool()

    shared = _shared_l0_count(src_name, dst_name)
    assert shared == _EXPECTED_SHARED_BLOCKS, (
        f'expected {_EXPECTED_SHARED_BLOCKS} shared L0 blocks '
        f'(1 MiB / {_VOLBLOCKSIZE}), got {shared}'
    )
