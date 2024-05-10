import os
import pytest
import stat

from middlewared.plugins.filesystem_ import stat_x as sx


BASIC_STAT_ATTRS = [
    'MODE',
    'UID',
    'GID',
    'ATIME',
    'MTIME',
    'CTIME',
    'DEV',
    'INO',
    'SIZE',
    'BLOCKS',
    'BLKSIZE',
    'NLINK',
]

def timespec_convert(timespec):
    return timespec.tv_sec + timespec.tv_nsec / 1000000000


def do_stat(filename, isdir):
    if not isdir:
        with open(filename, "w"):
            pass

    return (os.stat(filename), sx.statx(filename))


def validate_stat(stat_prop, st1, st2):
    match stat_prop:
        case 'MODE':
            assert st1.st_mode == st2.stx_mode
        case 'UID':
            assert st1.st_uid == st2.stx_uid
        case 'GID':
            assert st1.st_gid == st2.stx_gid
        case 'ATIME':
            assert st1.st_atime == timespec_convert(st2.stx_atime)
        case 'MTIME':
            assert st1.st_mtime == timespec_convert(st2.stx_mtime)
        case 'CTIME':
            assert st1.st_ctime == timespec_convert(st2.stx_ctime)
        case 'INO':
            assert st1.st_ino == st2.stx_ino
        case 'DEV':
            assert st1.st_dev == os.makedev(st2.stx_dev_major, st2.stx_dev_minor)
        case 'BLOCKS':
            assert st1.st_blocks == st2.stx_blocks
        case 'BLKSIZE':
            assert st1.st_blksize == st2.stx_blksize
        case 'NLINK':
            assert st1.st_nlink == st2.stx_nlink
        case 'SIZE':
            assert st1.st_size == st2.stx_size
        case _:
            raise ValueError(f'{stat_prop}: unknown stat property')


@pytest.mark.parametrize('stat_prop', BASIC_STAT_ATTRS)
def test__check_statx_vs_stat_file(tmpdir, stat_prop):
    st1, st2 = do_stat(os.path.join(tmpdir, 'testfile'), False)
    validate_stat(stat_prop, st1, st2)


@pytest.mark.parametrize('stat_prop', BASIC_STAT_ATTRS)
def test__check_statx_vs_stat_dir(tmpdir, stat_prop):
    st1, st2 = do_stat(str(tmpdir), True)
    validate_stat(stat_prop, st1, st2)


def test__check_dirfd(tmpdir):
    testfile = os.path.join(tmpdir, 'testfile')
    with open(testfile, 'w'):
        pass

    stx1 = sx.statx(testfile)
    try:
        dirfd = os.open(tmpdir, os.O_PATH)
        stx2 = sx.statx('testfile', {'dir_fd': dirfd})
    finally:
        os.close(dirfd)

    assert stx1.stx_ino == stx2.stx_ino


def test__check_statx_empty_path(tmpdir):
    # test fstat equivalent via statx interface
    testfile = os.path.join(tmpdir, 'testfile')
    with open(testfile, 'w'):
        pass

    stx1 = sx.statx(testfile)
    try:
        fd = os.open(testfile, os.O_PATH)
        stx2 = sx.statx('', {'dir_fd': fd, 'flags': sx.ATFlags.EMPTY_PATH})
    finally:
        os.close(fd)

    assert stx1.stx_ino == stx2.stx_ino
