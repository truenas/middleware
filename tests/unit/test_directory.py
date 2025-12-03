import gc
import os
import pytest
import stat

from middlewared.utils.filter_list import filter_list
from middlewared.utils.filesystem import constants
from middlewared.utils.filesystem import directory


TEST_FILES = [
    'testfile1',
    'testfile2',
    'canary',
    '1234_bob'
]

TEST_DIRS = [
    'testdir1',
    'testdir2',
    '1234_larry'
]

@pytest.fixture(scope="function")
def directory_for_test(tmpdir):
    for filename in TEST_FILES:
        path = os.path.join(tmpdir, filename)
        with open(path, 'w'):
            pass

        os.symlink(path, os.path.join(tmpdir, f'{filename}_sl'))

    for dirname in TEST_DIRS:
        path = os.path.join(tmpdir, dirname)
        os.mkdir(path)

        os.symlink(path, os.path.join(tmpdir, f'{dirname}_sl'))

    return tmpdir


def validate_attributes(dirent):
    assert dirent['name'] is not None
    assert dirent['path'] is not None
    assert dirent['realpath'] is not None

    st = os.stat(dirent['realpath'])
    assert dirent['size'] == st.st_size
    assert dirent['mode'] == st.st_mode
    assert dirent['uid'] == st.st_uid
    assert dirent['gid'] == st.st_gid
    assert dirent['allocation_size'] == st.st_blocks * 512

    match dirent['type']:
        case 'DIRECTORY':
            assert stat.S_ISDIR(dirent['mode'])
            assert dirent['name'] == os.path.basename(dirent['realpath'])
            assert dirent['path'] == dirent['realpath']
        case 'FILE':
            assert stat.S_ISREG(dirent['mode'])
            assert dirent['name'] == os.path.basename(dirent['realpath'])
            assert dirent['path'] == dirent['realpath']
        case 'SYMLINK':
            assert dirent['name'] != os.path.basename(dirent['realpath'])
            assert dirent['path'] != dirent['realpath']
            # we do not check mode here because we follow symlink for stat output
            # for directory entry
        case _:
            raise ValueError(f'{dirent["type"]}: unexpected dirent type')


def test__length_no_filters(directory_for_test):
    dir_iter = directory.DirectoryIterator(directory_for_test)
    assert len(filter_list(dir_iter, [], {})) == 2 * len(TEST_FILES + TEST_DIRS)

    dir_iter.close()


def test__length_iter_dirs(directory_for_test):
    assert len(filter_list(
        directory.DirectoryIterator(directory_for_test, file_type=constants.FileType.DIRECTORY),
        [], {}
    )) == len(TEST_DIRS)

    assert len(filter_list(
        directory.DirectoryIterator(directory_for_test),
        [['type', '=', 'DIRECTORY']], {}
    )) == len(TEST_DIRS)

    gc.collect()


def test__length_iter_files(directory_for_test):
    assert len(filter_list(
        directory.DirectoryIterator(directory_for_test, file_type=constants.FileType.FILE),
        [], {}
    )) == len(TEST_FILES)

    assert len(filter_list(
        directory.DirectoryIterator(directory_for_test),
        [['type', '=', 'FILE']], {}
    )) == len(TEST_FILES)


def test__length_iter_symlink(directory_for_test):
    expected_symlinks = len(TEST_FILES) + len(TEST_DIRS)

    assert len(filter_list(
        directory.DirectoryIterator(directory_for_test, file_type=constants.FileType.SYMLINK),
        [], {}
    )) == expected_symlinks

    assert len(filter_list(
        directory.DirectoryIterator(directory_for_test),
        [['type', '=', 'SYMLINK']], {}
    )) == expected_symlinks


def test__stat_attributes_dirents(directory_for_test):
    dir_iter = directory.DirectoryIterator(directory_for_test)
    for dirent in dir_iter:
        validate_attributes(dirent)


def test__directory_zero_request_mask(directory_for_test):
    dir_iter = directory.DirectoryIterator(directory_for_test, request_mask=0)
    for dirent in dir_iter:
        assert dirent['realpath'] is None
        assert dirent['is_ctldir'] is None
        assert dirent['zfs_attrs'] is None
        assert dirent['xattrs'] is None
        assert dirent['acl'] is None

    del(dir_iter)
    gc.collect()


def test__directory_realpath_request_mask(directory_for_test):
    dir_iter = directory.DirectoryIterator(directory_for_test, request_mask=directory.DirectoryRequestMask.REALPATH)
    for dirent in dir_iter:
        assert dirent['realpath'] is not None
        assert dirent['is_ctldir'] is None
        assert dirent['zfs_attrs'] is None
        assert dirent['xattrs'] is None
        assert dirent['acl'] is None


def test__directory_xattrs_request_mask(directory_for_test):
    dir_iter = directory.DirectoryIterator(directory_for_test, request_mask=directory.DirectoryRequestMask.XATTRS)
    for dirent in dir_iter:
        assert dirent['realpath'] is None
        assert dirent['is_ctldir'] is None
        assert dirent['zfs_attrs'] is None
        assert dirent['xattrs'] is not None
        assert dirent['acl'] is None


def test__directory_acl_request_mask(directory_for_test):
    with directory.DirectoryIterator(directory_for_test, request_mask=directory.DirectoryRequestMask.ACL) as dir_iter:
        for dirent in dir_iter:
            assert dirent['realpath'] is None
            assert dirent['is_ctldir'] is None
            assert dirent['zfs_attrs'] is None
            assert dirent['xattrs'] is None
            assert dirent['acl'] is not None


def test__directory_request_mask():
    for entry in directory.DirectoryRequestMask:
        assert entry in directory.ALL_ATTRS

    for entry in directory.ALL_ATTRS:
        assert directory.DirectoryRequestMask(entry)


def test__directory_is_empty(tmpdir):
    gc.collect()
    assert directory.directory_is_empty(tmpdir)
    os.mkdir(os.path.join(tmpdir, 'testfile'))
    assert not directory.directory_is_empty(tmpdir)


def test__directory_fd(directory_for_test):
    # without dir_fd specified (open(2))
    dfd = directory.DirectoryFd(directory_for_test)

    # basic smoke-test of __repr__ for the DirectoryFd objec
    assert str(directory_for_test) in repr(dfd)

    # with dir_fd specified (openat(2) with relative path).
    dfd2 = directory.DirectoryFd('testdir1', dir_fd=dfd.fileno)
    assert 'testdir1' in repr(dfd2)

    dfd.close()
    assert dfd.fileno is None

    with pytest.raises(NotADirectoryError):
        directory.DirectoryFd(os.path.join(directory_for_test, 'testfile1'))
