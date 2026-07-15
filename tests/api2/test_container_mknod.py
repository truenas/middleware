import time

import pytest

from middlewared.test.integration.assets.container import (
    UBUNTU_IMAGE_NAME,
    configure_bridge,
    container,
    nsenter,
    resolve_image,
)
from middlewared.test.integration.utils import ssh


@pytest.fixture(scope="module", autouse=True)
def bridge():
    configure_bridge()


@pytest.fixture(scope="module")
def ubuntu_image():
    yield resolve_image(UBUNTU_IMAGE_NAME)


def test_privileged_allow_container_can_create_device_nodes(ubuntu_image):
    """A privileged "Allow All" container can create device nodes via mknod.

    ``capabilities_policy=ALLOW`` on a privileged (``idmap=None``) container
    injects ``<mknod state='on'/>``, which makes libvirt widen the LXC cgroup
    device ACL. That widening is what lets a nested container runtime create the
    device nodes it needs when extracting image layers (overlay whiteouts):
    without it the cgroup device controller denies ``mknod`` of a
    non-whitelisted device with EPERM, even though CAP_MKNOD is in the bounding
    set. This checks that gating operation directly rather than by pulling a
    whole image.

    The device controller is enforced by cgroup membership, so the ``mknod``
    must run under the container's OWN cgroup. A bare ``nsenter`` from the host
    enters the namespaces but stays in the host cgroup and would bypass the ACL
    (a false pass), so the probe is launched via ``systemd-run`` inside the
    container, which places it under the container's cgroup.
    """
    with container(
        ubuntu_image,
        {"idmap": None, "capabilities_policy": "ALLOW"},
        start=True,
    ) as c:
        probe = (
            "systemd-run --scope --quiet /bin/sh -c "
            "'rm -f /tmp/mknod-probe; mknod /tmp/mknod-probe b 7 0'"
        )
        # Retry briefly: the container's systemd (which systemd-run talks to)
        # may still be coming up right after start.
        for _ in range(15):
            result = ssh(nsenter(c, probe), check=False, complete_response=True)
            if result["returncode"] == 0:
                break
            time.sleep(2)

        assert result["returncode"] == 0, result["output"]
