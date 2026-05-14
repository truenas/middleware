"""
Unit tests for middlewared.utils.filesystem.perms — enforce_dir_perms and
enforce_mountpoint_perms.

These helpers wrap openat2(RESOLVE_NO_SYMLINKS) + stat-first conditional
fchmod/fchown to set a fixed (mode, uid, gid) on a directory in a
symlink-safe way. enforce_mountpoint_perms additionally gates on
STATX_ATTR_MOUNT_ROOT.

The tests use pytest's tmp_path; they do not touch ZFS or the data pool.
"""

import errno
import os
from unittest.mock import patch

import pytest

from middlewared.utils.filesystem.perms import enforce_dir_perms, enforce_mountpoint_perms


def _mode(path):
    return os.stat(path).st_mode & 0o7777


def test_enforce_dir_perms_sets_mode(tmp_path):
    d = tmp_path / 'd'
    d.mkdir()
    os.chmod(d, 0o755)

    enforce_dir_perms(str(d))

    assert _mode(d) == 0o700


def test_enforce_dir_perms_respects_custom_mode(tmp_path):
    d = tmp_path / 'd'
    d.mkdir()

    enforce_dir_perms(str(d), mode=0o750)

    assert _mode(d) == 0o750


def test_enforce_dir_perms_stat_first_is_noop_when_correct(tmp_path):
    d = tmp_path / 'd'
    d.mkdir()
    os.chmod(d, 0o700)
    st = os.stat(d)

    # Helper must not call fchmod or fchown when mode + ownership already match.
    # Pass the dir's actual owner so the no-op path is hit even when the test
    # runs as non-root.
    with patch('os.fchmod', side_effect=AssertionError('fchmod should not be called')), \
            patch('os.fchown', side_effect=AssertionError('fchown should not be called')):
        enforce_dir_perms(str(d), mode=0o700, uid=st.st_uid, gid=st.st_gid)


def test_enforce_dir_perms_rejects_symlink_component(tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(target)

    with pytest.raises(OSError) as ei:
        enforce_dir_perms(str(link))

    assert ei.value.errno == errno.ELOOP


def test_enforce_dir_perms_raises_on_missing(tmp_path):
    with pytest.raises(OSError) as ei:
        enforce_dir_perms(str(tmp_path / 'does_not_exist'))

    assert ei.value.errno == errno.ENOENT


def test_enforce_mountpoint_perms_rejects_regular_dir(tmp_path):
    # tmp_path is on the same filesystem as its parent — not a mount root.
    with pytest.raises(OSError) as ei:
        enforce_mountpoint_perms(str(tmp_path))

    assert ei.value.errno == errno.ENOTDIR


def test_enforce_mountpoint_perms_rejects_symlink_component(tmp_path):
    target = tmp_path / 'target'
    target.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(target)

    with pytest.raises(OSError) as ei:
        enforce_mountpoint_perms(str(link))

    assert ei.value.errno == errno.ELOOP
