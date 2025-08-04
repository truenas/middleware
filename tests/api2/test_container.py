import json
import re

import pytest
import requests
import websocket

from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh, websocket_url

VIRSH = "virsh -c 'lxc:///system?socket=/run/truenas_libvirt/libvirt-sock'"


@pytest.fixture(scope="module")
def images_dataset():
    with dataset("images") as ds:
        call("container.config.update", {"image_dataset": ds})
        yield ds


@pytest.fixture(scope="module")
def ubuntu_image(images_dataset):
    base_url = "https://images.linuxcontainers.org/images/ubuntu/plucky/amd64/default"
    recent_version = re.findall(r'href="(.+)"', requests.get(f"{base_url}/").text)[-1]
    url = f"{base_url}/{recent_version}/rootfs.tar.xz"

    call("container.image.pull", url, "ubuntu", job=True)
    yield f"{images_dataset}/ubuntu@image"


@pytest.fixture(scope="function")
def container(ubuntu_image):
    dataset = f"{pool}/container"
    call("pool.snapshot.clone", {"snapshot": ubuntu_image, "dataset_dst": dataset})
    try:
        container = call("container.create", {
            "name": "test",
            "memory": 128,
            "dataset": dataset,
            "init": "/sbin/init",
        })
        try:
            yield container
        finally:
            call("container.delete", container["id"])

            #  Id   Name   State
            # --------------------
            assert len(ssh(f"{VIRSH} list --all").strip().splitlines()) == 2
    finally:
        call("pool.dataset.delete", dataset)


@pytest.fixture(scope="function")
def started_container(container):
    call("container.start", container["id"])

    container = call("container.get_instance", container["id"])
    assert container["status"]["state"] == "RUNNING"
    assert "/sbin/init" in ssh(f"ps -p {container['status']['pid']} -o args")

    yield container


def test_container_stop(started_container):
    call("container.stop", started_container["id"])

    container = call("container.get_instance", started_container["id"])
    assert container["status"]["state"] == "STOPPED"
    assert container["status"]["pid"] is None
    assert (
        ssh(f"ps -p {started_container['status']['pid']}", check=False, complete_response=True)["returncode"] == 1
    )


def test_container_update(started_container):
    call("container.update", started_container["id"], {"init": "/bin/sleep infinity"})

    container = call("container.get_instance", started_container["id"])
    assert "/sbin/init" in ssh(f"ps -p {container['status']['pid']} -o args")

    call("container.stop", started_container["id"])

    call("container.start", started_container["id"])

    container = call("container.get_instance", started_container["id"])
    assert "/bin/sleep infinity" in ssh(f"ps -p {container['status']['pid']} -o args")


def test_container_stop_force_after_timeout(container):
    call("container.update", container["id"], {"init": "/bin/sleep infinity", "shutdown_timeout": 5})

    call("container.start", container["id"])
    container = call("container.get_instance", container["id"])
    assert container["status"]["state"] == "RUNNING"

    call("container.stop", container["id"])
    container = call("container.get_instance", container["id"])
    assert container["status"]["state"] == "RUNNING"  # Process with PID=1 ignores SIGTERM if it is not init

    call("container.stop", container["id"], {"force_after_timeout": True})
    container = call("container.get_instance", container["id"])
    assert container["status"]["state"] == "STOPPED"


def test_container_shell(started_container):
    ssh(f"touch /mnt/{started_container['dataset']}/mnt/canary")
    token = call("auth.generate_token", 300, {}, False)
    ws = websocket.create_connection(websocket_url() + "/websocket/shell")
    try:
        ws.send(json.dumps({
            "token": token,
            "options": {"container_id": started_container["id"], "command": ["ls", "/mnt"]}
        }))
        resp_opcode, msg = ws.recv_data()
        assert json.loads(msg.decode())["msg"] == "connected", msg

        data = ""
        ws.settimeout(30)
        for i in range(60):
            try:
                resp_opcode, msg = ws.recv_data()
            except Exception as e:
                print(e)
                break

            data += msg.decode("ascii", "ignore")

        assert data.replace("\x03", "").strip().split()[-1] == f"canary"
    finally:
        ws.close()
