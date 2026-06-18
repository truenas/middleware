import pytest

from middlewared.plugins.vm.crud import _is_secboot_firmware


@pytest.mark.parametrize(
    "filename,expected",
    [
        # OVMF secboot variants
        ("OVMF_CODE.secboot.fd", True),
        ("OVMF_CODE_4M.secboot.fd", True),
        ("OVMF_CODE_4M.secboot.strictnx.fd", True),
        ("OVMF_CODE_4M.ms.fd", True),  # symlink to secboot
        ("OVMF_CODE_4M.snakeoil.fd", True),  # self-signed secboot variant
        # AAVMF secboot variants
        ("AAVMF_CODE.secboot.fd", True),
        ("AAVMF_CODE.secboot.strictnx.fd", True),
        ("AAVMF_CODE.ms.fd", True),  # symlink to secboot
        ("AAVMF_CODE.snakeoil.fd", True),  # symlink to secboot
        # Non-secboot variants
        ("OVMF_CODE.fd", False),
        ("OVMF_CODE_4M.fd", False),
        ("AAVMF_CODE.fd", False),
        ("AAVMF_CODE.no-secboot.fd", False),  # 'no-secboot' is the negation; anchored match avoids the false positive
    ],
)
def test_is_secboot_firmware(filename, expected):
    assert _is_secboot_firmware(filename) is expected
