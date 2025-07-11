import json
import re
import time

import pytest
import requests
import websocket

from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh, websocket_url


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


def test_container(ubuntu_image):
    dataset = f"{pool}/container"
    call("pool.snapshot.clone", {"snapshot": ubuntu_image, "dataset_dst": dataset})
    try:
        container = call("container.create", {
            "name": "test",
            "memory": 128,
            "dataset": dataset,
            "init": "/bin/sleep infinity",
        })

        call("container.start", container["id"])
        container = call("container.get_instance", container["id"])

        assert "/bin/sleep infinity" in ssh(f"ps -p {container['status']['pid']} -o args")

        ssh(f"touch /mnt/{dataset}/mnt/canary")
        token = call("auth.generate_token", 300, {}, False)
        ws = websocket.create_connection(websocket_url() + "/websocket/shell")
        try:
            ws.send(json.dumps({
                "token": token,
                "options": {"container_id": container["id"], "command": ["ls", "/mnt"]}
            }))
            resp_opcode, msg = ws.recv_data()
            assert json.loads(msg.decode())["msg"] == "connected", msg

            data = ""
            ws.settimeout(1)
            for i in range(60):
                try:
                    resp_opcode, msg = ws.recv_data()
                except Exception:
                    break

                data += msg.decode("ascii", "ignore")

            assert data.strip().split()[-1] == "canary"
        finally:
            ws.close()

        ssh(f"kill -9 {container['status']['pid']}")
        time.sleep(5)
        print(ssh("ps ax"))
    finally:
        call("pool.dataset.delete", dataset)
