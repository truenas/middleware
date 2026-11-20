import os
import shutil

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.utils.path import check_path_resides_within_volume_sync, symlink_in_path


@pytest.fixture(scope="function")
def setup_mnt(tmpdir):
    os.makedirs('/mnt/pool/foo')
    os.mkdir('/mnt/foo')
    try:
        os.symlink(tmpdir, '/mnt/pool/symlink')
        os.symlink('/mnt/foo', '/mnt/pool/symlink2')
        yield
    finally:
        shutil.rmtree('/mnt/pool')
        os.rmdir('/mnt/foo')


@pytest.mark.parametrize("path,should_raise", [
    ('/tmp', True),
    ('EXTERNAL://smb_server.local/SHARE', True),
    ('/mnt', True),
    ('/mnt/does_not_exist', True),
    ('/mnt/foo', True),
    ('/mnt/pool/foo', False),
    ('/mnt/pool', False),
    ('/mnt/pool/..', True),
    ('/mnt/pool/symlink', True),
    ('/mnt/pool/symlink2', True)
])
def test___check_path_resides_within_volume(setup_mnt, path, should_raise):
    volumes = ['pool']
    verr = ValidationErrors()
    check_path_resides_within_volume_sync(verr, "test.path", path, volumes)
    if should_raise:
        with pytest.raises(ValidationErrors):
            verr.check()
    else:
        verr.check()


@pytest.fixture
def symlink_tree(tmp_path):
    (tmp_path / 'dir').mkdir()
    (tmp_path / 'dir' / 'file').touch()
    (tmp_path / 'link').symlink_to(tmp_path / 'dir')
    (tmp_path / 'dangling').symlink_to(tmp_path / 'missing')
    return tmp_path


@pytest.mark.parametrize('path,expected', [
    ('dir', False),
    ('dir/file', False),
    ('missing', False),
    ('missing/file', False),
    ('link', True),
    ('link/file', True),
    ('link/missing', True),
    ('dangling', True),
])
def test_symlink_in_path(symlink_tree, path, expected):
    assert symlink_in_path(str(symlink_tree / path)) is expected


def test_symlink_in_path_raises_other_errors(symlink_tree):
    with pytest.raises(NotADirectoryError):
        symlink_in_path(str(symlink_tree / 'dir' / 'file' / 'x'))
