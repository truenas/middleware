import gc
import os
import pytest
import stat
import threading

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
    assert dirent.name is not None
    assert dirent.path is not None
    assert dirent.realpath is not None

    st = os.stat(dirent.realpath)
    assert dirent.size == st.st_size
    assert dirent.mode == st.st_mode
    assert dirent.uid == st.st_uid
    assert dirent.gid == st.st_gid
    assert dirent.allocation_size == st.st_blocks * 512

    match dirent.type:
        case 'DIRECTORY':
            assert stat.S_ISDIR(dirent.mode)
            assert dirent.name == os.path.basename(dirent.realpath)
            assert dirent.path == dirent.realpath
        case 'FILE':
            assert stat.S_ISREG(dirent.mode)
            assert dirent.name == os.path.basename(dirent.realpath)
            assert dirent.path == dirent.realpath
        case 'SYMLINK':
            assert dirent.name != os.path.basename(dirent.realpath)
            assert dirent.path != dirent.realpath
            # we do not check mode here because we follow symlink for stat output
            # for directory entry
        case _:
            raise ValueError(f'{dirent["type"]}: unexpected dirent type')


def test__length_no_filters(directory_for_test):
    assert len(filter_list(
        directory.iter_listdir(directory_for_test), [], {}, directory.FilesystemDirEntry,
    )) == 2 * len(TEST_FILES + TEST_DIRS)


def test__length_iter_dirs(directory_for_test):
    assert len(filter_list(
        directory.iter_listdir(directory_for_test, file_type=constants.FileType.DIRECTORY),
        [], {}, directory.FilesystemDirEntry,
    )) == len(TEST_DIRS)

    assert len(filter_list(
        directory.iter_listdir(directory_for_test),
        [['type', '=', 'DIRECTORY']], {}, directory.FilesystemDirEntry,
    )) == len(TEST_DIRS)

    gc.collect()


def test__length_iter_files(directory_for_test):
    assert len(filter_list(
        directory.iter_listdir(directory_for_test, file_type=constants.FileType.FILE),
        [], {}, directory.FilesystemDirEntry,
    )) == len(TEST_FILES)

    assert len(filter_list(
        directory.iter_listdir(directory_for_test),
        [['type', '=', 'FILE']], {}, directory.FilesystemDirEntry,
    )) == len(TEST_FILES)


def test__length_iter_symlink(directory_for_test):
    expected_symlinks = len(TEST_FILES) + len(TEST_DIRS)

    assert len(filter_list(
        directory.iter_listdir(directory_for_test, file_type=constants.FileType.SYMLINK),
        [], {}, directory.FilesystemDirEntry,
    )) == expected_symlinks

    assert len(filter_list(
        directory.iter_listdir(directory_for_test),
        [['type', '=', 'SYMLINK']], {}, directory.FilesystemDirEntry,
    )) == expected_symlinks


def test__stat_attributes_dirents(directory_for_test):
    for dirent in directory.iter_listdir(directory_for_test):
        validate_attributes(dirent)


def test__directory_zero_request_mask(directory_for_test):
    for dirent in directory.iter_listdir(directory_for_test, request_mask=directory.DirectoryRequestMask(0)):
        assert dirent.realpath is None
        assert dirent.is_ctldir is None
        assert dirent.zfs_attrs is None
        assert dirent.xattrs is None
        assert dirent.acl is None


def test__directory_realpath_request_mask(directory_for_test):
    for dirent in directory.iter_listdir(
        directory_for_test, request_mask=directory.DirectoryRequestMask.REALPATH
    ):
        assert dirent.realpath is not None
        assert dirent.is_ctldir is None
        assert dirent.zfs_attrs is None
        assert dirent.xattrs is None
        assert dirent.acl is None


def test__directory_xattrs_request_mask(directory_for_test):
    for dirent in directory.iter_listdir(
        directory_for_test, request_mask=directory.DirectoryRequestMask.XATTRS
    ):
        assert dirent.realpath is None
        assert dirent.is_ctldir is None
        assert dirent.zfs_attrs is None
        assert dirent.xattrs is not None
        assert dirent.acl is None


def test__directory_acl_request_mask(directory_for_test):
    for dirent in directory.iter_listdir(
        directory_for_test, request_mask=directory.DirectoryRequestMask.ACL
    ):
        assert dirent.realpath is None
        assert dirent.is_ctldir is None
        assert dirent.zfs_attrs is None
        assert dirent.xattrs is None
        assert dirent.acl is not None


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


def test__iter_listdir_skips_unresolvable_symlinks(tmpdir):
    open(os.path.join(tmpdir, 'file'), 'w').close()
    os.symlink('missing', os.path.join(tmpdir, 'dangling'))
    os.symlink('loop', os.path.join(tmpdir, 'loop'))
    os.symlink('file/child', os.path.join(tmpdir, 'notdir'))

    assert [dirent.name for dirent in directory.iter_listdir(tmpdir)] == ['file']


def test__iter_listdir_symlink_to_fifo(tmpdir):
    os.mkfifo(os.path.join(tmpdir, 'fifo'))
    os.symlink('fifo', os.path.join(tmpdir, 'fifo_sl'))
    listed = {}

    def listdir():
        listed.update((dirent.name, dirent) for dirent in directory.iter_listdir(tmpdir))

    thread = threading.Thread(target=listdir, daemon=True)
    thread.start()
    thread.join(30)
    assert not thread.is_alive(), 'listing the directory blocked'
    assert listed['fifo_sl'].type == 'SYMLINK'
    assert stat.S_ISFIFO(listed['fifo_sl'].mode)
