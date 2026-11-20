import tarfile

import pytest

from middlewared.plugins.container.query_pull_images import rootfs_filter


@pytest.mark.parametrize('name', ['../escape', 'a/../../escape'])
def test_rejects_member_outside_dest(tmp_path, name):
    with pytest.raises(tarfile.OutsideDestinationError):
        rootfs_filter(tarfile.TarInfo(name), str(tmp_path))


def test_strips_leading_slash(tmp_path):
    assert rootfs_filter(tarfile.TarInfo('/etc/passwd'), str(tmp_path)).name == 'etc/passwd'


def test_rejects_write_through_symlink(tmp_path):
    (tmp_path / 'etc').symlink_to('/etc')
    with pytest.raises(tarfile.OutsideDestinationError):
        rootfs_filter(tarfile.TarInfo('etc/shadow'), str(tmp_path))


@pytest.mark.parametrize('name,mode', [('usr/bin/sudo', 0o4755), ('tmp', 0o1777)])
def test_keeps_mode(tmp_path, name, mode):
    member = tarfile.TarInfo(name)
    member.mode = mode
    assert rootfs_filter(member, str(tmp_path)).mode == mode
