import time

import pytest

from middlewared.test.integration.assets.iscsi import iscsi_extent
from middlewared.test.integration.assets.nvmet import nvmet_namespace, nvmet_subsys
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

MiB = 1024 * 1024


def wait_for_link(path: str, timeout: int = 20) -> None:
    for _ in range(timeout * 10):
        if ssh(f"test -e {path} && echo yes || echo no").strip() == "yes":
            return
        time.sleep(0.1)
    pytest.fail(f"{path!r} never appeared")


def test_unlocked_zvols_fast_without_arguments():
    """Every argument is optional and defaults to an empty filter"""
    with dataset("test_uzf_plain", {"type": "VOLUME", "volsize": MiB}) as zvol:
        wait_for_link(f"/dev/zvol/{zvol}")
        result = call("zfs.resource.unlocked_zvols_fast")
        entry = [r for r in result if r["name"] == zvol]
        assert len(entry) == 1
        assert entry[0]["path"] == f"/dev/zvol/{zvol}"
        assert entry[0]["dev"].startswith("zd")
        assert "size" not in entry[0]


def test_unlocked_zvols_fast_name_with_space():
    """A space in the zvol name is escaped as '+' in its /dev/zvol path"""
    with dataset("test uzf space", {"type": "VOLUME", "volsize": MiB}) as zvol:
        escaped = f"/dev/zvol/{zvol.replace(' ', '+')}"
        wait_for_link(escaped)
        result = call("zfs.resource.unlocked_zvols_fast", [["name", "=", zvol]])
        assert len(result) == 1
        assert result[0]["path"] == escaped


def test_unlocked_zvols_fast_skips_partition_links():
    """A partitioned zvol reports the whole device, never its partitions"""
    with dataset("test_uzf_parts") as container:
        ssh(f"zfs set volmode=full {container}")
        with dataset("test_uzf_parts/zvol", {"type": "VOLUME", "volsize": 100 * MiB}) as zvol:
            ssh(f"sgdisk -n 1:1MiB:2MiB /dev/zvol/{zvol}")
            ssh(f"partprobe /dev/zvol/{zvol} || true")
            wait_for_link(f"/dev/zvol/{zvol}-part1")

            result = call("zfs.resource.unlocked_zvols_fast", [["name", "^", zvol]])
            assert [r["name"] for r in result] == [zvol]


def test_unlocked_zvols_fast_skips_regular_files():
    """A regular file under /dev/zvol is not a zvol and is skipped"""
    with dataset("test_uzf_regfile", {"type": "VOLUME", "volsize": MiB}) as zvol:
        wait_for_link(f"/dev/zvol/{zvol}")
        pool = zvol.split("/")[0]
        stray = f"/dev/zvol/{pool}/test_uzf_stray_file"
        ssh(f"touch {stray}")
        try:
            result = call("zfs.resource.unlocked_zvols_fast")
            names = [r["name"] for r in result]
            assert zvol in names
            assert f"{pool}/test_uzf_stray_file" not in names
        finally:
            ssh(f"rm -f {stray}")


def test_unlocked_zvols_fast_reports_extra_information():
    with dataset("test_uzf_extra", {"type": "VOLUME", "volsize": MiB}) as zvol:
        wait_for_link(f"/dev/zvol/{zvol}")
        result = call(
            "zfs.resource.unlocked_zvols_fast",
            [["name", "=", zvol]],
            {},
            ["SIZE", "DEVID", "RO"],
        )
        assert len(result) == 1
        assert result[0]["size"] == MiB
        assert result[0]["ro"] is False
        assert ":" in result[0]["devid"]


def test_unlocked_zvols_fast_reports_iscsi_attachment():
    with dataset("test_uzf_iscsi", {"type": "VOLUME", "volsize": MiB}) as zvol:
        wait_for_link(f"/dev/zvol/{zvol}")
        with iscsi_extent({"name": "test_uzf_extent", "type": "DISK", "disk": f"zvol/{zvol}"}):
            result = call(
                "zfs.resource.unlocked_zvols_fast",
                [["name", "=", zvol]],
                {},
                ["ATTACHMENT"],
            )
            assert len(result) == 1
            assert result[0]["attachment"]["method"] == "iscsi.extent.query"
            assert result[0]["attachment"]["data"]["path"] == f"zvol/{zvol}"


def test_unlocked_zvols_fast_reports_no_attachment_when_unused():
    with dataset("test_uzf_unused", {"type": "VOLUME", "volsize": MiB}) as zvol:
        wait_for_link(f"/dev/zvol/{zvol}")
        result = call(
            "zfs.resource.unlocked_zvols_fast",
            [["name", "=", zvol]],
            {},
            ["ATTACHMENT"],
        )
        assert len(result) == 1
        assert result[0]["attachment"] is None


def test_unlocked_zvols_fast_reports_nvmet_attachment():
    with dataset("test_uzf_nvmet", {"type": "VOLUME", "volsize": MiB}) as zvol:
        wait_for_link(f"/dev/zvol/{zvol}")
        with nvmet_subsys("test_uzf_subsys") as subsys:
            with nvmet_namespace(subsys["id"], f"zvol/{zvol}"):
                result = call(
                    "zfs.resource.unlocked_zvols_fast",
                    [["name", "=", zvol]],
                    {},
                    ["ATTACHMENT"],
                )
                assert len(result) == 1
                assert result[0]["attachment"]["method"] == "nvmet.namespace.query"
