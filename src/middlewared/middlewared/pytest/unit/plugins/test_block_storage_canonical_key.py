import pytest

from middlewared.common.block_storage import canonical_key


@pytest.mark.parametrize(
    "path,expected",
    [
        # iSCSI and NVMe-oF spell a zvol `zvol/pool/name`, VM devices `/dev/zvol/pool/name`
        ("zvol/tank/vol", "tank/vol"),
        ("/dev/zvol/tank/vol", "tank/vol"),
        # udev spells a space in a zvol name as `+`
        ("zvol/tank/my vol", "tank/my vol"),
        ("zvol/tank/my+vol", "tank/my vol"),
        ("/dev/zvol/tank/my+vol", "tank/my vol"),
        ("zvol/tank/vol@snap", "tank/vol@snap"),
    ],
)
def test_zvol_spellings_share_a_key(path, expected):
    assert canonical_key("ZVOL", path) == ("ZVOL", expected)


def test_snapshot_is_not_its_origin():
    assert canonical_key("ZVOL", "zvol/tank/vol@snap") != canonical_key("ZVOL", "/dev/zvol/tank/vol")


def test_existing_file_resolves_symlinks(tmp_path):
    target = tmp_path / "disk.img"
    target.write_bytes(b"")
    link = tmp_path / "link.img"
    link.symlink_to(target)

    assert canonical_key("FILE", str(link)) == ("FILE", str(target.resolve()))
    assert canonical_key("FILE", str(link)) == canonical_key("FILE", str(target))


@pytest.mark.parametrize("spelling", ["sub//disk.img", "sub/./disk.img", "sub/other/../disk.img"])
def test_absent_file_is_normalized(tmp_path, spelling):
    assert canonical_key("FILE", f"{tmp_path}/{spelling}") == ("FILE", f"{tmp_path}/sub/disk.img")


def test_kind_is_part_of_the_key():
    assert canonical_key("FILE", "/dev/zvol/tank/vol") != canonical_key("ZVOL", "/dev/zvol/tank/vol")
