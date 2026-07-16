import contextlib
import json
import re
import secrets
import time

import pytest
import websocket

from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.utils import call, ssh, websocket_url
from auto_config import interface

_vm_password = secrets.token_urlsafe(16)

IMAGES = {
    "amd64": "https://cloud-images.ubuntu.com/questing/current/questing-server-cloudimg-amd64.img",
    "arm64": "https://cloud-images.ubuntu.com/questing/current/questing-server-cloudimg-arm64.img",
}

# Extra vm.create kwargs for non-default-arch guests.
VM_ARCH_OPTIONS = {
    "amd64": {},
    "arm64": {
        "arch_type": "aarch64",
        "machine_type": "virt-9.2",
        "cpu_mode": "CUSTOM",
        "cpu_model": "cortex-a53",
    },
}

# AAVMF has no AHCI driver; arm64 guests must boot from a VirtIO disk.
VM_DISK_TYPE = {
    "amd64": "AHCI",
    "arm64": "VIRTIO",
}

# Set this to false when debugging to prevent test image snapshots from being destroyed when the
# test ends, and then re-downloaded on the next test launch.
DELETE_IMAGE_SNAPSHOTS = True

# arm64 runs under TCG (software emulation) on x86 hosts — boot takes several minutes.
pytestmark = pytest.mark.timeout(1200)


def ssh_vm(vm, *args, **kwargs):
    return ssh(*args, **kwargs, user="root", ip=vm["ip"], password=vm["password"])


@pytest.fixture(scope="module")
def vm_test_pool():
    with another_pool() as pool:
        yield pool["name"]


@pytest.fixture(scope="module", params=["amd64", "arm64"])
def ubuntu_image_snapshot(request, vm_test_pool):
    arch = request.param
    image_url = IMAGES[arch]
    snapshot_name = f"{vm_test_pool}/ubuntu-{arch}@pristine"
    if call("pool.snapshot.query", [["name", "=", snapshot_name]]):
        yield {"snapshot": snapshot_name, "arch": arch, "pool": vm_test_pool}
    else:
        ssh(f"wget {image_url}")

        qcow2_image_name = image_url.split("/")[-1]
        image_name = qcow2_image_name.rsplit(".", 1)[0] + ".raw"
        ssh(f"qemu-img convert -f qcow2 -O raw {qcow2_image_name} {image_name}")
        ssh(f"rm {qcow2_image_name}")

        try:
            with dataset(
                f"ubuntu-{arch}",
                {"type": "VOLUME", "volsize": 4 * 1024**3},
                pool=vm_test_pool,
                delete=DELETE_IMAGE_SNAPSHOTS,
            ) as volume_name:
                volume_path = f"/dev/zvol/{volume_name}"
                ssh(f"dd if={image_name} of={volume_path} bs=16M")
                ssh(f"rm {image_name}")

                loop_device = ssh("losetup -f").strip()
                ssh(f"losetup -P {loop_device} {volume_path}")
                try:
                    ssh("mkdir -p rootfs")
                    try:
                        ssh(f"mount {loop_device}p1 rootfs")
                        try:
                            ssh(
                                r'sed -i "s/^#\?PermitRootLogin.*/PermitRootLogin yes/" rootfs/etc/ssh/sshd_config'
                            )
                            ssh(
                                r'sed -i "s/^#\?PasswordAuthentication.*/PasswordAuthentication yes/" '
                                "rootfs/etc/ssh/sshd_config"
                            )
                            ssh(
                                r"rm rootfs/etc/ssh/sshd_config.d/60-cloudimg-settings.conf"
                            )
                            ssh("ssh-keygen -A -f rootfs")
                            ssh(
                                rf'PASS=$(openssl passwd -6 "{_vm_password}") && sed -i "s|^root:[^:]*:|root:$PASS:|" rootfs/etc/shadow'
                            )
                            ssh(
                                "echo '[Match]' > rootfs/etc/systemd/network/99-wildcard.network"
                            )
                            ssh(
                                "echo 'Name=en*' >> rootfs/etc/systemd/network/99-wildcard.network"
                            )
                            ssh(
                                "echo '[Network]' >> rootfs/etc/systemd/network/99-wildcard.network"
                            )
                            ssh(
                                "echo 'DHCP=yes' >> rootfs/etc/systemd/network/99-wildcard.network"
                            )
                        finally:
                            ssh("umount rootfs")

                        call(
                            "pool.snapshot.create",
                            {"dataset": volume_name, "name": "pristine"},
                        )
                        yield {
                            "snapshot": f"{volume_name}@pristine",
                            "arch": arch,
                            "pool": vm_test_pool,
                        }
                    finally:
                        ssh("rm -rf rootfs")
                finally:
                    ssh(f"losetup -d {loop_device}")
        finally:
            ssh(f"rm -f {image_name}")


@contextlib.contextmanager
def ubuntu_vm(image_info, options=None):
    arch = image_info["arch"]
    snapshot = image_info["snapshot"]
    test_pool = image_info["pool"]
    vm_dataset = f"{test_pool}/vm-{arch}"
    call("pool.snapshot.clone", {"snapshot": snapshot, "dataset_dst": vm_dataset})
    try:
        vm = call(
            "vm.create",
            {
                "name": f"Test_{arch}",
                "memory": 2048,
                **VM_ARCH_OPTIONS[arch],
                **(options or {}),
            },
        )
        try:
            call(
                "vm.device.create",
                {
                    "vm": vm["id"],
                    "attributes": {
                        "dtype": "NIC",
                        "nic_attach": interface,
                    },
                },
            )
            call(
                "vm.device.create",
                {
                    "vm": vm["id"],
                    "attributes": {
                        "dtype": "DISK",
                        "type": VM_DISK_TYPE[arch],
                        "path": f"/dev/zvol/{vm_dataset}",
                    },
                },
            )

            call("vm.start", vm["id"])

            token = call("auth.generate_token", 300, {}, False)
            ws = websocket.create_connection(websocket_url() + "/websocket/shell")
            ip_address = None
            try:
                ws.send(json.dumps({"token": token, "options": {"vm_id": vm["id"]}}))
                resp_opcode, msg = ws.recv_data()
                assert json.loads(msg.decode())["msg"] == "connected", msg

                data = b""
                login_sent = False
                password_sent = False
                ip_sent = False
                ws.settimeout(600 if arch == "arm64" else 30)
                while True:
                    try:
                        resp_opcode, msg = ws.recv_data()
                    except Exception as e:
                        print(e)
                        break

                    data += msg

                    if not login_sent and data.endswith(b"login: "):
                        ws.send_binary(b"root\r\n")
                        login_sent = True
                    if not password_sent and data.endswith(b"Password: "):
                        ws.send_binary(_vm_password.encode("ascii") + b"\r\n")
                        password_sent = True
                    if not ip_sent and data.endswith(b"root@ubuntu:~# "):
                        ws.send_binary(
                            b"NO_COLOR=1 ip -4 -o addr show scope global\r\n"
                        )
                        ip_sent = True
                    if m := re.search(
                        r"inet ([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
                        data.decode("ascii", "ignore"),
                    ):
                        ip_address = m.group(1)
                        break
            finally:
                ws.close()

            if ip_address is None:
                raise RuntimeError(
                    "Unable to find IP address: "
                    + data.decode("ascii", "ignore")[-1000:]
                )

            deadline = time.monotonic() + 60
            while True:
                try:
                    ssh("true", user="root", ip=ip_address, password=_vm_password)
                    break
                except Exception:
                    if time.monotonic() > deadline:
                        raise RuntimeError(f"SSH on {ip_address} not ready after 60s")
                    time.sleep(5)

            yield {**vm, "ip": ip_address, "password": _vm_password}
        finally:
            call("vm.delete", vm["id"], {"force": True})
    finally:
        call("pool.dataset.delete", vm_dataset)


def test_vm(ubuntu_image_snapshot):
    with ubuntu_vm(ubuntu_image_snapshot) as vm:
        assert "Ubuntu" in ssh_vm(vm, "cat /etc/issue")
