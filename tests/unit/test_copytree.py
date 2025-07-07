import errno
import gc
import os
import pytest
import random
import stat

from middlewared.utils.filesystem import copy
from operator import eq, ne
from unittest.mock import Mock, patch

TEST_FILE_DATASZ = 128 * 1024
TEST_XATTR_DATASZ = 1024

TEST_FILES = [
    ('testfile1', random.randbytes(TEST_FILE_DATASZ)),
    ('testfile2', random.randbytes(TEST_FILE_DATASZ)),
    ('canary', random.randbytes(TEST_FILE_DATASZ)),
    ('1234_bob', random.randbytes(TEST_FILE_DATASZ))
]

TEST_FILE_XATTRS = [
    ('user.filexat1', random.randbytes(TEST_XATTR_DATASZ)),
    ('user.filexat2', random.randbytes(TEST_XATTR_DATASZ)),
    ('user.filexat3', random.randbytes(TEST_XATTR_DATASZ)),
]

TEST_DIRS = [
    'testdir1',
    'testdir2',
    '1234_larry'
]

TEST_DIR_XATTRS = [
    ('user.dirxat1', random.randbytes(TEST_XATTR_DATASZ)),
    ('user.dirxat2', random.randbytes(TEST_XATTR_DATASZ)),
    ('user.dirxat3', random.randbytes(TEST_XATTR_DATASZ)),
]

JENNY = 8675309


class Job:
    log = []
    progress = 0

    def set_progress(self, progress: int, msg: str):
        self.progress = progress
        self.log.append(msg)


def create_test_files(target: str, symlink_target_path: str) -> None:
    for filename, data in TEST_FILES:
        path = os.path.join(target, filename)
        with open(path, 'wb') as f:
            f.write(data)
            os.fchmod(f.fileno(), 0o666)
            os.fchown(f.fileno(), JENNY, JENNY + 1)
            f.flush()

        for xat_name, xat_data in TEST_FILE_XATTRS:
            os.setxattr(path, xat_name, xat_data)

        # symlink target outside of dirs to be copied around
        sl = f'{filename}_sl'
        os.symlink(symlink_target_path, os.path.join(target, sl))

        # this needs to be last op on file to avoid having other
        # changes affect atime / mtime
        os.utime(path, ns=(JENNY + 1, JENNY + 2))


def create_test_data(target: str, symlink_target_path) -> None:
    """ generate test data in randomized temporary directory

    Basic tree of files and directories including some symlinks
    """
    source = os.path.join(target, 'SOURCE')
    os.mkdir(source)

    for xat_name, xat_data in TEST_DIR_XATTRS:
        os.setxattr(source, xat_name, xat_data)

    os.chown(source, JENNY + 10, JENNY + 11)
    os.chmod(source, 0o777)

    create_test_files(source, symlink_target_path)

    for dirname in TEST_DIRS:
        path = os.path.join(source, dirname)
        os.mkdir(path)
        os.chmod(path, 0o777)
        os.chown(path, JENNY, JENNY)

        for xat_name, xat_data in TEST_DIR_XATTRS:
            os.setxattr(path, xat_name, xat_data)

        # force atime and mtime to some value other than
        # current timestamp
        os.utime(path, ns=(JENNY + 3, JENNY + 4))

        # symlink target outside of dirs to be copied around
        sl = f'{dirname}_sl'
        os.symlink(symlink_target_path, os.path.join(path, sl))

        # create separate symlink dir for our test files
        # _outside_ SOURCE
        os.mkdir(os.path.join(target, dirname))
        create_test_files(path, os.path.join(target, dirname))
        os.utime(path, ns=(JENNY + 3, JENNY + 4))

    os.utime(source, ns=(JENNY + 5, JENNY + 6))


@pytest.fixture(scope="function")
def directory_for_test(tmpdir):
    """ generate test data in randomized temporary directory

    Basic tree of files and directories including some symlinks
    """
    create_test_data(tmpdir, tmpdir)
    return tmpdir


def validate_attributes(
    src: str,
    dst: str,
    flags: copy.CopyFlags
) -> None:
    st_src = os.lstat(src)
    st_dst = os.lstat(dst)

    assert st_src.st_size == st_dst.st_size

    match (file_type := stat.S_IFMT(st_src.st_mode)):
        case stat.S_IFREG | stat.S_IFDIR:
            pass
            # validate we set owner / group when requested
            op = eq if flags & copy.CopyFlags.OWNER else ne
            assert op(st_src.st_uid, st_dst.st_uid)
            assert op(st_src.st_gid, st_dst.st_gid)

            # validate we preserve file mode when requested
            op = eq if flags & copy.CopyFlags.PERMISSIONS else ne
            assert op(st_src.st_mode, st_dst.st_mode)

            # validate we preserve timestamps when requested
            op = eq if flags & copy.CopyFlags.TIMESTAMPS else ne

            # checking mtime is sufficient. Atime in test runner
            # is enabled and so it will get reset on source when
            # we're copying data around.
            assert op(st_src.st_mtime_ns, st_dst.st_mtime_ns)
        case stat.S_IFLNK:
            src_tgt = os.readlink(src)
            dst_tgt = os.readlink(dst)
            assert eq(src_tgt, dst_tgt)
            return
        case _:
            raise ValueError(f'{src}: unexpected file type: {file_type}')

    # validate we set owner / group when requested
    op = eq if flags & copy.CopyFlags.OWNER else ne
    assert op(st_src.st_uid, st_dst.st_uid)
    assert op(st_src.st_gid, st_dst.st_gid)

    # validate we preserve file mode when requested
    op = eq if flags & copy.CopyFlags.PERMISSIONS else ne
    assert op(st_src.st_mode, st_dst.st_mode)

    # validate we preserve timestamps when requested
    # NOTE: futimens on linux only allows setting atime + mtime
    op = eq if flags & copy.CopyFlags.TIMESTAMPS else ne
    assert op(st_src.st_mtime_ns, st_dst.st_mtime_ns)


def validate_xattrs(
    src: str,
    dst: str,
    flags: copy.CopyFlags
) -> None:
    if stat.S_ISLNK(os.lstat(src).st_mode):
        # Nothing to do since we don't follow symlinks
        return

    xat_src = os.listxattr(src)
    xat_dst = os.listxattr(dst)

    if flags & copy.CopyFlags.XATTRS:
        assert len(xat_src) > 0
        assert len(xat_dst) > 0
        assert xat_src == xat_dst

        for xat_name in xat_src:
            xat_data_src = os.getxattr(src, xat_name)
            xat_data_dst = os.getxattr(dst, xat_name)

            assert len(xat_data_src) > 0

            assert xat_data_src == xat_data_dst

    else:
        assert len(xat_src) > 0
        assert len(xat_dst) == 0


def validate_data(
    src: str,
    dst: str,
    flags: copy.CopyFlags
) -> None:
    match (file_type := stat.S_IFMT(os.lstat(src).st_mode)):
        case stat.S_IFLNK:
            # readlink performed in validate_attributes
            return

        case stat.S_IFDIR:
            assert set(os.listdir(src)) == set(os.listdir(dst))
            return

        case stat.S_IFREG:
            # validation performed below
            pass

        case _:
            raise ValueError(f'{src}: unexpected file type: {file_type}')

    with open(src, 'rb') as f:
        src_data = f.read()

    with open(dst, 'rb') as f:
        dst_data = f.read()

    assert src_data == dst_data


def validate_the_things(
    src: str,
    dst: str,
    flags: copy.CopyFlags
) -> None:
    for fn in (validate_data, validate_xattrs, validate_attributes):
        fn(src, dst, flags)


def validate_copy_tree(
    src: str,
    dst: str,
    flags: copy.CopyFlags
):
    with os.scandir(src) as it:
        for f in it:
            if f.name == 'CHILD':
                # skip validation of bind mountpoint
                continue

            new_src = os.path.join(src, f.name)
            new_dst = os.path.join(dst, f.name)
            validate_the_things(new_src, new_dst, flags)
            if f.is_dir() and not f.is_symlink():
                validate_copy_tree(new_src, new_dst, flags)

    validate_the_things(src, dst, flags)


def test__copytree_default(directory_for_test):
    """ test basic behavior of copytree """

    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'DEST')
    config = copy.CopyTreeConfig()

    assert config.flags == copy.DEF_CP_FLAGS

    stats = copy.copytree(src, dst, config)

    validate_copy_tree(src, dst, config.flags)
    assert stats.files != 0
    assert stats.dirs != 0
    assert stats.symlinks != 0


@pytest.mark.parametrize('is_ctldir', [True, False])
def test__copytree_exclude_ctldir(directory_for_test, is_ctldir):
    """ test that we do not recurse into ZFS ctldir """

    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'DEST')

    snapdir = os.path.join(src, '.zfs', 'snapshot', 'now')
    os.makedirs(snapdir)
    with open(os.path.join(snapdir, 'canary'), 'w'):
        pass

    if is_ctldir:
        # Mock over method to determine whether path is in actual .zfs
        with patch(
            'middlewared.utils.filesystem.copy.path_in_ctldir', Mock(
                return_value=True
            )
        ):
            copy.copytree(src, dst, copy.CopyTreeConfig())

        # We should automatically exclude a real .zfs directory
        assert not os.path.exists(os.path.join(dst, '.zfs'))
    else:
        # This .zfs directory does not have special inode number
        # and so we know we can copy it.
        copy.copytree(src, dst, copy.CopyTreeConfig())
        assert os.path.exists(os.path.join(dst, '.zfs'))


@pytest.mark.parametrize('existok', [True, False])
def test__copytree_existok(directory_for_test, existok):
    """ test behavior of `exist_ok` configuration option """

    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'DEST')
    config = copy.CopyTreeConfig(exist_ok=existok)
    os.mkdir(dst)

    if existok:
        copy.copytree(src, dst, config)
        validate_copy_tree(src, dst, config.flags)

    else:
        with pytest.raises(FileExistsError):
            copy.copytree(src, dst, config)


@pytest.mark.parametrize('flag', [
    copy.CopyFlags.XATTRS,
    copy.CopyFlags.PERMISSIONS,
    copy.CopyFlags.TIMESTAMPS,
    copy.CopyFlags.OWNER
])
def test__copytree_flags(directory_for_test, flag):
    """
    copytree allows user to specify what types of metadata to
    preserve on copy similar to robocopy on Windows. This tests
    that setting individual flags results in copy of _only_
    the specified metadata.
    """

    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'DEST')
    copy.copytree(src, dst, copy.CopyTreeConfig(flags=flag))

    validate_copy_tree(src, dst, flag)


def test__force_userspace_copy(directory_for_test):
    """ force use of shutil.copyfileobj wrapper instead of copy_file_range """

    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'DEST')
    flags = copy.DEF_CP_FLAGS

    copy.copytree(src, dst, copy.CopyTreeConfig(flags=flags, op=copy.CopyTreeOp.USERSPACE))

    validate_copy_tree(src, dst, flags)


def test__copytree_into_itself_simple(directory_for_test):
    """ perform a basic copy of a tree into a subdirectory of itself.
    This simulates case where user has mistakenly set homedir to FOO
    and performs an update of homedir to switch it to FOO/username.

    If logic breaks then we'll end up with this test failing due to
    infinite recursion.
    """
    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'SOURCE', 'DEST')

    copy.copytree(src, dst, copy.CopyTreeConfig())

    assert not os.path.exists(os.path.join(directory_for_test, 'SOURCE', 'DEST', 'DEST'))


def test__copytree_into_itself_complex(directory_for_test):
    """ check recursion guard against deeper nested target """

    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'SOURCE', 'FOO', 'BAR', 'DEST')

    os.makedirs(os.path.join(directory_for_test, 'SOURCE', 'FOO', 'BAR'))

    copy.copytree(src, dst, copy.CopyTreeConfig())

    # we expect to copy everything up to the point where we'd start infinite
    # recursion
    assert os.path.exists(os.path.join(dst, 'FOO', 'BAR'))

    # but not quite get there
    assert not os.path.exists(os.path.join(dst, 'FOO', 'BAR', 'DEST'))


def test__copytree_job_log(directory_for_test):
    """ check that providing job object causes progress to be written properly """
    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'DEST')
    job = Job()

    config = copy.CopyTreeConfig(job=job, job_msg_inc=1)
    copy.copytree(src, dst, config)

    assert job.progress == 100
    assert len(job.log) > 0
    last = job.log[-1]

    assert last.startswith('Successfully copied')


def test__copytree_job_log_prefix(directory_for_test):
    """ check that log message prefix gets written as expected """
    src = os.path.join(directory_for_test, 'SOURCE')
    dst = os.path.join(directory_for_test, 'DEST')
    job = Job()

    config = copy.CopyTreeConfig(job=job, job_msg_inc=1, job_msg_prefix='Canary: ')
    copy.copytree(src, dst, config)

    assert job.progress == 100
    assert len(job.log) > 0
    last = job.log[-1]

    assert last.startswith('Canary: Successfully copied')


def test__clone_file_somewhat_large(tmpdir):

    src_fd = os.open(os.path.join(tmpdir, 'test_large_clone_src'), os.O_CREAT | os.O_RDWR)
    dst_fd = os.open(os.path.join(tmpdir, 'test_large_clone_dst'), os.O_CREAT | os.O_RDWR)
    chunk_sz = 1024 ** 2

    try:
        for i in range(0, 128):
            payload = random.randbytes(chunk_sz)
            os.pwrite(src_fd, payload, i * chunk_sz)

        copy.clone_file(src_fd, dst_fd)

        for i in range(0, 128):
            src = os.pread(src_fd, chunk_sz, i * chunk_sz)
            dst = os.pread(dst_fd, chunk_sz, i * chunk_sz)
            assert src == dst

    finally:
        os.close(src_fd)
        os.close(dst_fd)
        os.unlink(os.path.join(tmpdir, 'test_large_clone_src'))
        os.unlink(os.path.join(tmpdir, 'test_large_clone_dst'))


def test__copy_default_fallthrough(tmpdir):
    """ verify we can fallthrough from CLONE to USERSPACE """
    src_fd = os.open(os.path.join(tmpdir, 'test_default_fallthrough_src'), os.O_CREAT | os.O_RDWR)
    dst_fd = os.open(os.path.join(tmpdir, 'test_default_fallthrough_dst'), os.O_CREAT | os.O_RDWR)
    chunk_sz = 1024 ** 2

    try:
        for i in range(0, 128):
            payload = random.randbytes(chunk_sz)
            os.pwrite(src_fd, payload, i * chunk_sz)

        # return value of 0 triggers fallthrough code
        with patch('os.sendfile', Mock(return_value=0)):

            # raising EXDEV triggers clone fallthrough
            with patch('middlewared.utils.filesystem.copy.clone_file', Mock(side_effect=OSError(errno.EXDEV, 'MOCK'))):
                copy.clone_or_copy_file(src_fd, dst_fd)

        for i in range(0, 128):
            src = os.pread(src_fd, chunk_sz, i * chunk_sz)
            dst = os.pread(dst_fd, chunk_sz, i * chunk_sz)
            assert src == dst

    finally:
        os.close(src_fd)
        os.close(dst_fd)
        os.unlink(os.path.join(tmpdir, 'test_default_fallthrough_src'))
        os.unlink(os.path.join(tmpdir, 'test_default_fallthrough_dst'))


def test__copy_sendfile_fallthrough(tmpdir):
    """ verify that fallthrough to userspace copy from copy_sendfile works """
    src_fd = os.open(os.path.join(tmpdir, 'test_sendfile_fallthrough_src'), os.O_CREAT | os.O_RDWR)
    dst_fd = os.open(os.path.join(tmpdir, 'test_sendfile_fallthrough_dst'), os.O_CREAT | os.O_RDWR)
    chunk_sz = 1024 ** 2

    try:
        for i in range(0, 128):
            payload = random.randbytes(chunk_sz)
            os.pwrite(src_fd, payload, i * chunk_sz)

        # return value of 0 triggers fallthrough code
        with patch('os.sendfile', Mock(return_value=0)):
            copy.copy_sendfile(src_fd, dst_fd)

        for i in range(0, 128):
            src = os.pread(src_fd, chunk_sz, i * chunk_sz)
            dst = os.pread(dst_fd, chunk_sz, i * chunk_sz)
            assert src == dst

    finally:
        os.close(src_fd)
        os.close(dst_fd)
        os.unlink(os.path.join(tmpdir, 'test_sendfile_fallthrough_src'))
        os.unlink(os.path.join(tmpdir, 'test_sendfile_fallthrough_dst'))


def test__copy_sendfile(tmpdir):
    """ verify that copy.sendfile preserves file data and does not by default fallthrogh to userspace """
    src_fd = os.open(os.path.join(tmpdir, 'test_large_sendfile_src'), os.O_CREAT | os.O_RDWR)
    dst_fd = os.open(os.path.join(tmpdir, 'test_large_sendfile_dst'), os.O_CREAT | os.O_RDWR)
    chunk_sz = 1024 ** 2

    try:
        for i in range(0, 128):
            payload = random.randbytes(chunk_sz)
            os.pwrite(src_fd, payload, i * chunk_sz)

        with patch(
            'middlewared.utils.filesystem.copy.copy_file_userspace', Mock(
                side_effect=Exception('Unexpected fallthrough to copy_userspace')
            )
        ):
            copy.copy_sendfile(src_fd, dst_fd)

        for i in range(0, 128):
            src = os.pread(src_fd, chunk_sz, i * chunk_sz)
            dst = os.pread(dst_fd, chunk_sz, i * chunk_sz)
            assert src == dst

    finally:
        os.close(src_fd)
        os.close(dst_fd)
        os.unlink(os.path.join(tmpdir, 'test_large_sendfile_src'))
        os.unlink(os.path.join(tmpdir, 'test_large_sendfile_dst'))
