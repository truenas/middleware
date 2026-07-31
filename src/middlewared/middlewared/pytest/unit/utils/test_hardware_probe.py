import os

import pytest

from middlewared.utils.hardware import probe


@pytest.fixture
def scsi_generic(tmp_path, monkeypatch):
    """Build a fake /sys/class/scsi_generic tree and point the probe at it."""

    def build(models: dict[str, str]):
        for name, model in models.items():
            device = tmp_path / name / "device"
            device.mkdir(parents=True)
            (device / "model").write_text(f"{model}\n")
        monkeypatch.setattr(probe, "_SCSI_GENERIC_MODEL_GLOB", f"{tmp_path}/*/device/model")
        return tmp_path

    return build


@pytest.mark.parametrize("model", ["TrueNAS_A", "TrueNAS_B"])
def test_ha_backplane_found(scsi_generic, model):
    scsi_generic({"sg0": "QEMU HARDDISK", "sg1": model})
    assert probe._bhyve_ha_backplane_present() is True


def test_unrelated_models_only(scsi_generic):
    scsi_generic({"sg0": "QEMU HARDDISK", "sg1": "Virtual disk"})
    assert probe._bhyve_ha_backplane_present() is False


def test_empty_tree(scsi_generic):
    scsi_generic({})
    assert probe._bhyve_ha_backplane_present() is False


def test_unreadable_file_does_not_raise(scsi_generic):
    root = scsi_generic({"sg0": "QEMU HARDDISK"})
    os.chmod(root / "sg0" / "device" / "model", 0o000)
    assert probe._bhyve_ha_backplane_present() is False


def test_unreadable_entry_does_not_hide_a_later_one(scsi_generic):
    """One bad entry must be skipped, not abort the whole scan."""
    root = scsi_generic({"sg0": "QEMU HARDDISK", "sg1": "TrueNAS_A"})
    # A directory where a file is expected raises IsADirectoryError regardless
    # of the uid running the tests, unlike chmod which root ignores.
    (root / "sg0" / "device" / "model").unlink()
    (root / "sg0" / "device" / "model").mkdir()
    assert probe._bhyve_ha_backplane_present() is True


def test_directory_in_place_of_model(scsi_generic):
    root = scsi_generic({"sg0": "QEMU HARDDISK"})
    (root / "sg0" / "device" / "model").unlink()
    (root / "sg0" / "device" / "model").mkdir()
    assert probe._bhyve_ha_backplane_present() is False
