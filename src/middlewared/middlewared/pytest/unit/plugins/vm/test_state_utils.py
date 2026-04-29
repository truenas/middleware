import errno
import os

import pytest

from middlewared.plugins.vm import utils as vm_utils
from middlewared.plugins.vm.utils import (
    delete_vm_state,
    get_vm_nvram_file_name,
    get_vm_tpm_state_dir_name,
    rename_vm_state,
    vm_nvram_path,
    vm_state_missing_sources,
    vm_tpm_path,
)


@pytest.fixture
def state_dirs(tmp_path, monkeypatch):
    nvram = tmp_path / "nvram"
    tpm = tmp_path / "tpm"
    nvram.mkdir()
    tpm.mkdir()
    monkeypatch.setattr(vm_utils, "SYSTEM_NVRAM_FOLDER_PATH", str(nvram))
    monkeypatch.setattr(vm_utils, "SYSTEM_TPM_FOLDER_PATH", str(tpm))
    return nvram, tpm


def _make_nvram(nvram_dir, id_: int, name: str, data: bytes = b"vars") -> str:
    path = os.path.join(str(nvram_dir), get_vm_nvram_file_name(id_, name))
    with open(path, "wb") as f:
        f.write(data)
    return path


def _make_tpm(tpm_dir, id_: int, name: str) -> str:
    path = os.path.join(str(tpm_dir), get_vm_tpm_state_dir_name(id_, name))
    os.mkdir(path)
    with open(os.path.join(path, "tpm2-00.permall"), "wb") as f:
        f.write(b"tpmstate")
    with open(os.path.join(path, ".lock"), "wb") as f:
        f.write(b"")
    return path


def test_rename_vm_state_moves_both_artefacts(state_dirs):
    nvram, tpm = state_dirs
    old_nvram = _make_nvram(nvram, 1, "foo")
    old_tpm = _make_tpm(tpm, 1, "foo")
    old_nvram_ino = os.stat(old_nvram).st_ino
    old_tpm_ino = os.stat(old_tpm).st_ino

    rename_vm_state(1, "foo", 1, "bar")

    new_nvram = vm_nvram_path(1, "bar")
    new_tpm = vm_tpm_path(1, "bar")
    assert not os.path.exists(old_nvram)
    assert not os.path.exists(old_tpm)
    assert os.path.exists(new_nvram)
    assert os.path.isdir(new_tpm)
    # Inode preserved → metadata (ownership, mode, xattrs) survived the rename.
    assert os.stat(new_nvram).st_ino == old_nvram_ino
    assert os.stat(new_tpm).st_ino == old_tpm_ino
    # TPM dir contents moved with the directory.
    assert os.path.exists(os.path.join(new_tpm, "tpm2-00.permall"))
    assert os.path.exists(os.path.join(new_tpm, ".lock"))


def test_rename_vm_state_missing_both_is_noop(state_dirs):
    # Never-booted VM: neither artefact exists. Should not raise.
    rename_vm_state(2, "foo", 2, "bar")
    nvram, tpm = state_dirs
    assert os.listdir(str(nvram)) == []
    assert os.listdir(str(tpm)) == []


def test_rename_vm_state_missing_tpm_only(state_dirs):
    nvram, _ = state_dirs
    _make_nvram(nvram, 3, "foo")
    rename_vm_state(3, "foo", 3, "bar")
    assert os.path.exists(vm_nvram_path(3, "bar"))


def test_rename_vm_state_missing_nvram_only(state_dirs):
    _, tpm = state_dirs
    _make_tpm(tpm, 4, "foo")
    rename_vm_state(4, "foo", 4, "bar")
    assert os.path.isdir(vm_tpm_path(4, "bar"))


def test_rename_vm_state_stale_destination_fails_without_moving(state_dirs):
    nvram, _ = state_dirs
    _make_nvram(nvram, 5, "foo", b"src")
    _make_nvram(nvram, 5, "bar", b"stale")  # pre-existing — must not be clobbered
    with pytest.raises(FileExistsError):
        rename_vm_state(5, "foo", 5, "bar")
    # Both files still present, contents untouched.
    with open(vm_nvram_path(5, "foo"), "rb") as f:
        assert f.read() == b"src"
    with open(vm_nvram_path(5, "bar"), "rb") as f:
        assert f.read() == b"stale"


def test_rename_vm_state_rolls_back_nvram_when_tpm_fails(state_dirs, monkeypatch):
    nvram, tpm = state_dirs
    _make_nvram(nvram, 6, "foo")
    _make_tpm(tpm, 6, "foo")
    # Pre-create a stale TPM destination so AT_RENAME_NOREPLACE fails on TPM.
    _make_tpm(tpm, 6, "bar")

    with pytest.raises(FileExistsError):
        rename_vm_state(6, "foo", 6, "bar")

    # NVRAM should be back under the old name; TPM original still at old name.
    assert os.path.exists(vm_nvram_path(6, "foo"))
    assert not os.path.exists(vm_nvram_path(6, "bar"))
    assert os.path.isdir(vm_tpm_path(6, "foo"))


def test_delete_vm_state_removes_both(state_dirs):
    nvram, tpm = state_dirs
    _make_nvram(nvram, 7, "foo")
    _make_tpm(tpm, 7, "foo")
    delete_vm_state(7, "foo")
    assert not os.path.exists(vm_nvram_path(7, "foo"))
    assert not os.path.exists(vm_tpm_path(7, "foo"))


def test_delete_vm_state_missing_both_is_noop(state_dirs):
    # Never-booted VM — neither artefact exists. Must not raise.
    delete_vm_state(8, "foo")


def test_delete_vm_state_nvram_only(state_dirs):
    nvram, _ = state_dirs
    _make_nvram(nvram, 9, "foo")
    delete_vm_state(9, "foo")
    assert not os.path.exists(vm_nvram_path(9, "foo"))


def test_delete_vm_state_tpm_only(state_dirs):
    _, tpm = state_dirs
    _make_tpm(tpm, 10, "foo")
    delete_vm_state(10, "foo")
    assert not os.path.exists(vm_tpm_path(10, "foo"))


def test_vm_state_missing_sources_reports_gaps(state_dirs):
    nvram, tpm = state_dirs
    _make_nvram(nvram, 11, "uefi_only")
    _make_tpm(tpm, 12, "tpm_only")

    assert vm_state_missing_sources(11, "uefi_only", "UEFI", tpm=True) == ["TPM"]
    assert vm_state_missing_sources(12, "tpm_only", "UEFI", tpm=True) == ["NVRAM"]
    assert vm_state_missing_sources(13, "neither", "UEFI", tpm=True) == ["NVRAM", "TPM"]
    # BIOS bootloader → NVRAM is never expected.
    assert vm_state_missing_sources(13, "neither", "BIOS", tpm=False) == []


def test_rename_rejects_symlink_parent(tmp_path, monkeypatch):
    # The real system dataset has no symlinks in the path; this test proves
    # that if a symlink is injected at the parent dir, RESOLVE_NO_SYMLINKS
    # blocks the rename entirely.
    real_nvram = tmp_path / "real_nvram"
    real_tpm = tmp_path / "real_tpm"
    real_nvram.mkdir()
    real_tpm.mkdir()
    link_nvram = tmp_path / "link_nvram"
    link_nvram.symlink_to(real_nvram)
    monkeypatch.setattr(vm_utils, "SYSTEM_NVRAM_FOLDER_PATH", str(link_nvram))
    monkeypatch.setattr(vm_utils, "SYSTEM_TPM_FOLDER_PATH", str(real_tpm))

    with pytest.raises(OSError) as ei:
        rename_vm_state(14, "foo", 14, "bar")
    assert ei.value.errno == errno.ELOOP
