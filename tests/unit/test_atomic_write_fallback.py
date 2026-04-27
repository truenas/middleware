"""Test coverage for ``atomic_write_fallback`` defined in ``truenas-initrd.py``.

The fallback is a stdlib-only stand-in for ``truenas_os_pyutils.io.atomic_write``
used during cross-BE upgrades where the target BE's ``truenas_os`` C extension
cannot be loaded under the host BE's python. The semantics exercised here mirror
the upstream ``atomic_write`` test suite at
``/CODE/claudedir/truens_pos/tests/utils/test_io.py`` so behavioural drift between
the two is easy to spot.

The module under test is loaded via ``importlib`` because ``truenas-initrd.py``
lives outside any python package and its filename contains a hyphen.
"""
import importlib.util
import os
import pathlib
import stat

import pytest


_TRUENAS_INITRD_PATH = pathlib.Path("/usr/local/bin/truenas-initrd.py")


def _load_truenas_initrd():
    spec = importlib.util.spec_from_file_location(
        "truenas_initrd_for_test", _TRUENAS_INITRD_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


atomic_write_fallback = _load_truenas_initrd().atomic_write_fallback


@pytest.fixture
def atomic_dir(tmp_path):
    return tmp_path


def test_creates_text_file(atomic_dir):
    target = str(atomic_dir / "new_text.txt")
    with atomic_write_fallback(target) as f:
        f.write("Hello, World!")
    with open(target) as f:
        assert f.read() == "Hello, World!"


def test_creates_binary_file(atomic_dir):
    target = str(atomic_dir / "new_binary.bin")
    with atomic_write_fallback(target, "wb") as f:
        f.write(b"binary data")
    with open(target, "rb") as f:
        assert f.read() == b"binary data"


def test_replaces_existing(atomic_dir):
    target = str(atomic_dir / "replace_existing.txt")
    with open(target, "w") as f:
        f.write("original")
    with atomic_write_fallback(target) as f:
        f.write("replaced")
    with open(target) as f:
        assert f.read() == "replaced"


def test_does_not_replace_on_exception(atomic_dir):
    target = str(atomic_dir / "no_replace_on_exc.txt")
    with open(target, "w") as f:
        f.write("original")

    with pytest.raises(ValueError):
        with atomic_write_fallback(target) as f:
            f.write("partial")
            raise ValueError("abort")

    with open(target) as f:
        assert f.read() == "original"


def test_cleans_up_temp_file_on_exception(atomic_dir):
    target = str(atomic_dir / "exc_cleanup.txt")

    with pytest.raises(RuntimeError):
        with atomic_write_fallback(target) as f:
            f.write("partial")
            raise RuntimeError("boom")

    leftovers = [p for p in atomic_dir.iterdir() if p.name.startswith(".atomic_write_")]
    assert leftovers == []
    assert not (atomic_dir / "exc_cleanup.txt").exists()


def test_sets_permissions(atomic_dir):
    target = str(atomic_dir / "perms_write.txt")
    with atomic_write_fallback(target, perms=0o600) as f:
        f.write("data")
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o600


def test_sets_executable_permissions(atomic_dir):
    target = str(atomic_dir / "exec_write.sh")
    with atomic_write_fallback(target, perms=0o755) as f:
        f.write("#!/bin/sh\n")
    assert stat.S_IMODE(os.stat(target).st_mode) == 0o755


def test_validates_mode(atomic_dir):
    target = str(atomic_dir / "mode_test.txt")
    for mode in ("r", "rb", "a", "r+", "wt"):
        with pytest.raises(ValueError, match="invalid mode"):
            with atomic_write_fallback(target, mode) as f:
                f.write("x")


def test_multiple_writes(atomic_dir):
    target = str(atomic_dir / "multi_write.txt")
    with atomic_write_fallback(target) as f:
        f.write("line1\n")
        f.write("line2\n")
    with open(target) as f:
        assert f.read() == "line1\nline2\n"


def test_default_tmppath_is_target_dirname(atomic_dir):
    # Subdir on same filesystem as atomic_dir; default tmppath should resolve to
    # this subdir (dirname of target) rather than to atomic_dir itself.
    subdir = atomic_dir / "sub"
    subdir.mkdir()
    target = str(subdir / "file.txt")

    with atomic_write_fallback(target) as f:
        f.write("payload")

    assert (subdir / "file.txt").read_text() == "payload"
    # Nothing left behind in the parent
    assert list(atomic_dir.iterdir()) == [subdir]


def test_explicit_tmppath(atomic_dir):
    # Mimics the script's pattern of passing a parent directory as tmppath when
    # the target's own dirname may not yet exist on disk.
    target_dir = atomic_dir / "deep" / "nested"
    target_dir.mkdir(parents=True)
    target = str(target_dir / "config")

    with atomic_write_fallback(target, tmppath=str(atomic_dir)) as f:
        f.write("cfg")

    assert (target_dir / "config").read_text() == "cfg"
    leftovers = [p for p in atomic_dir.iterdir() if p.name.startswith(".atomic_write_")]
    assert leftovers == []


def test_empty_write(atomic_dir):
    target = str(atomic_dir / "empty.txt")
    with atomic_write_fallback(target) as f:
        pass
    assert os.path.getsize(target) == 0
