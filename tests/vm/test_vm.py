import contextlib
import json
import re

import pytest
import websocket

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, pool, ssh, websocket_url
from middlewared.test.integration.utils.ssh import default_password
from auto_config import interface

IMAGE_URL = "https://cloud-images.ubuntu.com/plucky/current/plucky-server-cloudimg-amd64.img"
# Set this to false when debugging to prevent from test image snapshots from being destroyed when the test ends, and
# then re-downloaded on the next test launch.
DELETE_IMAGE_SNAPSHOTS = True


def ssh_vm(vm, *args, **kwargs):
    return ssh(*args, **kwargs, user="root", ip=vm["ip"])


@pytest.fixture(scope="module")
def ubuntu_image_snapshot():
    snapshot_name = f"{pool}/ubuntu@pristine"
    if call("pool.snapshot.query", [["name", "=", snapshot_name]]):
        yield snapshot_name
    else:
        ssh(f"wget {IMAGE_URL}")

        qcow2_image_name = IMAGE_URL.split("/")[-1]
        image_name = qcow2_image_name.rsplit(".", 1)[0] + ".raw"
        ssh(f"qemu-img convert -f qcow2 -O raw {qcow2_image_name} {image_name}")
        ssh(f"rm {qcow2_image_name}")

        with dataset(
            "ubuntu",
            {"type": "VOLUME", "volsize": 4 * 1024 ** 3},
            delete=DELETE_IMAGE_SNAPSHOTS,
        ) as volume_name:
            volume_path = f"/dev/zvol/{volume_name}"
            ssh(f"dd if={image_name} of={volume_path} bs=16M")
            ssh(f"rm {image_name}")

            loop_device = ssh("losetup -f").strip()
            ssh(f"losetup -P {loop_device} {volume_path}")
            try:
                ssh("mkdir rootfs")
                try:
                    ssh(f"mount {loop_device}p1 rootfs")
                    try:
                        ssh(r'sed -i "s/^#\?PermitRootLogin.*/PermitRootLogin yes/" rootfs/etc/ssh/sshd_config')
                        ssh(r'sed -i "s/^#\?PasswordAuthentication.*/PasswordAuthentication yes/" '
                            'rootfs/etc/ssh/sshd_config')
                        ssh(r'rm rootfs/etc/ssh/sshd_config.d/60-cloudimg-settings.conf')
                        ssh(r'chroot rootfs ssh-keygen -A')
                        ssh(rf'echo root:{default_password} | chroot rootfs chpasswd')
                        ssh("echo '[Match]' > rootfs/etc/systemd/network/99-wildcard.network")
                        ssh("echo 'Name=en*' >> rootfs/etc/systemd/network/99-wildcard.network")
                        ssh("echo '[Network]' >> rootfs/etc/systemd/network/99-wildcard.network")
                        ssh("echo 'DHCP=yes' >> rootfs/etc/systemd/network/99-wildcard.network")
                    finally:
                        ssh("umount rootfs")

                    snapshot_name = "pristine"
                    call("pool.snapshot.create", {"dataset": volume_name, "name": snapshot_name})
                    yield f"{volume_name}@{snapshot_name}"
                finally:
                    ssh("rm -rf rootfs")
            finally:
                ssh(f"losetup -d {loop_device}")


@contextlib.contextmanager
def ubuntu_vm(ubuntu_image_snapshot, options=None):
    dataset = f"{pool}/vm"
    call("pool.snapshot.clone", {"snapshot": ubuntu_image_snapshot, "dataset_dst": dataset})
    try:
        vm = call("vm.create", {
            "name": "Test",
            "memory": 2048,
            **(options or {}),
        })
        try:
            call("vm.device.create", {
                "vm": vm["id"],
                "attributes": {
                    "dtype": "NIC",
                    "nic_attach": interface,
                },
            })
            call("vm.device.create", {
                "vm": vm["id"],
                "attributes": {
                    "dtype": "DISK",
                    "path": f"/dev/zvol/{dataset}",
                },
            })

            call("vm.start", vm["id"])

            token = call("auth.generate_token", 300, {}, False)
            ws = websocket.create_connection(websocket_url() + "/websocket/shell")
            ip_address = None
            try:
                ws.send(json.dumps({
                    "token": token,
                    "options": {"vm_id": vm["id"]}
                }))
                resp_opcode, msg = ws.recv_data()
                assert json.loads(msg.decode())["msg"] == "connected", msg

                data = b""
                login_sent = False
                password_sent = False
                ip_sent = False
                ws.settimeout(30)
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
                        ws.send_binary(default_password.encode("ascii") + b"\r\n")
                        password_sent = True
                    if not ip_sent and data.endswith(b"root@ubuntu:~# "):
                        ws.send_binary(b"NO_COLOR=1 ip address list ens3\r\n")
                        ip_sent = True
                    if m := re.search("inet ([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", data.decode("ascii", "ignore")):
                        ip_address = m.group(1)
                        break
            finally:
                ws.close()

            if ip_address is None:
                raise RuntimeError("Unable to find IP address: " + data.decode("ascii", "ignore")[-1000:])

            yield {**vm, "ip": ip_address}
        finally:
            call("vm.delete", vm["id"])
    finally:
        call("pool.dataset.delete", dataset)


def test_vm(ubuntu_image_snapshot):
    with ubuntu_vm(ubuntu_image_snapshot) as vm:
        assert "Ubuntu" in ssh_vm(vm, "cat /etc/issue")
