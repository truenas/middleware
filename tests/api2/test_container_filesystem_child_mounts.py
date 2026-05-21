import contextlib

import pytest

from middlewared.test.integration.assets.container import (
    UBUNTU_IMAGE_NAME,
    configure_bridge,
    container,
    filesystem_device,
    nsenter,
    resolve_image,
)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


@pytest.fixture(scope="module", autouse=True)
def bridge():
    configure_bridge()


@pytest.fixture(scope="module")
def ubuntu_image():
    yield resolve_image(UBUNTU_IMAGE_NAME)


@contextlib.contextmanager
def parent_with_child_dataset():
    # Lays down a parent ZFS dataset with one auto-mounted child dataset
    # underneath, plus a sentinel file on each so callers can distinguish
    # "parent contents visible" from "child contents leaked".
    with dataset("childmount_parent", mode="0o777") as parent:
        parent_path = f"/mnt/{parent}"
        ssh(
            f": > {parent_path}/parent_sentinel && "
            f"chmod 0666 {parent_path}/parent_sentinel"
        )
        with dataset("childmount_parent/child", mode="0o777") as child:
            child_path = f"/mnt/{child}"
            ssh(
                f": > {child_path}/child_sentinel && "
                f"chmod 0666 {child_path}/child_sentinel"
            )
            yield {
                "parent_path": parent_path,
                "parent_sentinel": "parent_sentinel",
                "child_subdir": "child",
                "child_sentinel": "child_sentinel",
            }


@pytest.mark.parametrize(
    "idmap",
    [
        pytest.param({"type": "DEFAULT"}, id="default-idmap"),
        pytest.param({"type": "ISOLATED", "slice": 1}, id="isolated-idmap"),
    ],
)
def test_container_starts_with_filesystem_source_having_child_mounts(
    ubuntu_image,
    idmap,
):
    # Regression guard for truenas_pylibvirt fdce747: pre-fix, attaching a
    # parent ZFS dataset (with auto-mounted child datasets under it) as a
    # FilesystemDevice to an ISOLATED container failed with EINVAL during
    # MS_BIND because libvirt-LXC's non-recursive bind hit the locked child
    # submounts. The fix stages the source via open_tree + MS_SLAVE +
    # move_mount before libvirt sees it.
    with parent_with_child_dataset() as ds_info:
        with container(ubuntu_image, {"idmap": idmap}) as c:
            with filesystem_device(c["id"], ds_info["parent_path"], "/share"):
                call("container.start", c["id"])
                c = call("container.get_instance", c["id"])
                assert c["status"]["state"] == "RUNNING"

                ls_parent = ssh(nsenter(c, "ls /share")).split()
                assert ds_info["parent_sentinel"] in ls_parent

                # Documented trade-off: non-recursive bind hides child dataset
                # contents. The child mountpoint dir may or may not be visible,
                # but child_sentinel MUST NOT be reachable.
                ls_child = ssh(
                    nsenter(c, f"ls /share/{ds_info['child_subdir']}"),
                    check=False,
                    complete_response=True,
                )
                if ls_child["returncode"] == 0:
                    assert (
                        ds_info["child_sentinel"] not in ls_child["stdout"].split()
                    ), (
                        "Child dataset leaked into container despite non-recursive "
                        "bind staging (pylibvirt fdce747 trade-off regressed)"
                    )


def test_filesystem_child_mount_runtime_state_cleaned_on_stop(ubuntu_image):
    # The fix stages FilesystemDevice sources under /run/truenas_containers/
    # devices/<uuid>/<slug>. After container stop, pylibvirt's
    # runtime.cleanup_for_uuid (driven by the libvirt STOPPED event) removes
    # the staged tree. This test asserts both the "exists while running" and
    # "gone after stop" invariants on the VM.
    with parent_with_child_dataset() as ds_info:
        with container(
            ubuntu_image,
            {"idmap": {"type": "ISOLATED", "slice": 1}},
        ) as c:
            with filesystem_device(c["id"], ds_info["parent_path"], "/share"):
                call("container.start", c["id"])
                c = call("container.get_instance", c["id"])
                uuid = c["uuid"]
                staged_root = f"/run/truenas_containers/devices/{uuid}"

                running_check = ssh(
                    f"test -d {staged_root}",
                    check=False,
                    complete_response=True,
                )
                assert running_check["returncode"] == 0, (
                    f"{staged_root} missing while container is running"
                )

                call("container.stop", c["id"], {"force": True}, job=True)

                gone_check = ssh(
                    f"test -e {staged_root}",
                    check=False,
                    complete_response=True,
                )
                assert gone_check["returncode"] != 0, (
                    f"{staged_root} not cleaned up after container stop"
                )
