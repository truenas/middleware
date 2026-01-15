import base64
import contextlib
import itertools
import json
import re
import shlex
import textwrap
import time

import pytest
import websocket

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool, pool
from middlewared.test.integration.utils import call, host, ssh, websocket_url

UBUNTU_IMAGE_NAME = "ubuntu:plucky:amd64:default"
VIRSH = "virsh -c 'lxc:///system?socket=/run/truenas_libvirt/libvirt-sock'"
# Capabilities necessary to launch a basic LXC container from linuxcontainers.org
BASIC_CAPABILITIES = {
    # Capabilities enabled in a default docker container
    "chown": True,
    "dac_override": True,
    "fowner": True,
    "fsetid": True,
    "kill": True,
    "setgid": True,
    "setuid": True,
    "setpcap": True,
    "net_bind_service": True,
    "net_raw": True,
    "sys_chroot": True,
    "mknod": True,
    "audit_write": True,
    "setfcap": True,
    # systemd needs this to do `mount`
    "sys_admin": True,
}


def get_mountpoint(dataset):
    rv = call("zfs.resource.query", {"paths": [dataset], "properties": ["mountpoint"]})
    return rv[0]["properties"]["mountpoint"]["value"]


def nsenter(container, command):
    return shlex.join(call("container.nsenter", container) + [command])


def script_output(container):
    for i in range(30):
        result = ssh(nsenter(container, "cat /log"), check=False, complete_response=True)
        if result["returncode"] == 0:
            return result["stdout"]

        time.sleep(1)

    assert False, result["output"]


def bounding_set(capsh_print):
    return re.search("Bounding set =(.*)", capsh_print).group(1).strip().split(",")


@pytest.fixture(scope="module", autouse=True)
def bridge():
    call("lxc.update", {
        "v4_network": "10.47.214.0/24",
        "v6_network": "fd42:3656:7be9:e46c::0/64",
    })


@pytest.fixture(scope="module")
def ubuntu_image():
    images = call("container.image.query_registry")
    version = [image["versions"][-1]["version"] for image in images if image["name"] == UBUNTU_IMAGE_NAME][0]

    yield {"name": UBUNTU_IMAGE_NAME, "version": version}


@contextlib.contextmanager
def container(image, options=None, start=False, startup_script=None):
    options = options or {}

    container = call("container.create", {
        "name": "test",
        "pool": pool,
        "image": image,
        **options,
    }, job=True)
    try:
        mountpoint = get_mountpoint(container["dataset"])
        if startup_script is not None:
            ssh(f"mkdir -p {mountpoint}/var/spool/cron/crontabs")

            call(
                "filesystem.file_receive",
                f"{mountpoint}/var/spool/cron/crontabs/root",
                base64.b64encode(b"@reboot /script-wrapper.sh\n").decode("ascii"),
                {"mode": 0o600},
            )
            call(
                "filesystem.file_receive",
                f"{mountpoint}/script-wrapper.sh",
                base64.b64encode(textwrap.dedent("""\
                    #!/bin/sh
                    /script.sh > /.log 2>&1
                    mv /.log /log
                """).encode("ascii")).decode("ascii"),
                {"mode": 0o755},
            )
            call(
                "filesystem.file_receive",
                f"{mountpoint}/script.sh",
                base64.b64encode(startup_script.encode("ascii")).decode("ascii"),
                {"mode": 0o755},
            )

        if start:
            call("container.start", container["id"])

            container = call("container.get_instance", container["id"])
            assert container["status"]["state"] == "RUNNING"

        yield container
    finally:
        call("container.delete", container["id"])

        #  Id   Name   State
        # --------------------
        assert container["uuid"] not in ssh(f"{VIRSH} list --all")


@pytest.fixture(scope="function")
def ubuntu_container(ubuntu_image):
    with container(ubuntu_image) as c:
        yield c


@pytest.fixture(scope="function")
def started_ubuntu_container(ubuntu_container):
    call("container.start", ubuntu_container["id"])

    container = call("container.get_instance", ubuntu_container["id"])
    assert container["status"]["state"] == "RUNNING"
    assert "/sbin/init" in ssh(f"ps -p {container['status']['pid']} -o args")

    yield container


def test_container_stop(started_ubuntu_container):
    call("container.stop", started_ubuntu_container["id"], job=True)

    container = call("container.get_instance", started_ubuntu_container["id"])
    assert container["status"]["state"] == "STOPPED"
    assert container["status"]["pid"] is None
    assert (
        ssh(
            f"ps -p {started_ubuntu_container['status']['pid']}", check=False, complete_response=True,
        )["returncode"] == 1
    )


def test_container_update(started_ubuntu_container):
    call("container.update", started_ubuntu_container["id"], {"init": "/bin/sleep infinity"})

    container = call("container.get_instance", started_ubuntu_container["id"])
    assert "/sbin/init" in ssh(f"ps -p {container['status']['pid']} -o args")

    call("container.stop", started_ubuntu_container["id"], job=True)

    call("container.start", started_ubuntu_container["id"])

    container = call("container.get_instance", started_ubuntu_container["id"])
    assert "/bin/sleep infinity" in ssh(f"ps -p {container['status']['pid']} -o args")


def test_container_stop_force_after_timeout(ubuntu_container):
    container = ubuntu_container

    call("container.update", container["id"], {"init": "/bin/sleep infinity", "shutdown_timeout": 5})

    call("container.start", container["id"])
    container = call("container.get_instance", container["id"])
    assert container["status"]["state"] == "RUNNING"

    call("container.stop", container["id"], job=True)
    container = call("container.get_instance", container["id"])
    assert container["status"]["state"] == "RUNNING"  # Process with PID=1 ignores SIGTERM if it is not init

    call("container.stop", container["id"], {"force_after_timeout": True}, job=True)
    container = call("container.get_instance", container["id"])
    assert container["status"]["state"] == "STOPPED"


def test_container_shell(started_ubuntu_container):
    mountpoint = get_mountpoint(started_ubuntu_container["dataset"])
    ssh(f"touch {mountpoint}/mnt/canary")
    token = call("auth.generate_token", 300, {}, False)
    ws = websocket.create_connection(websocket_url() + "/websocket/shell")
    try:
        ws.send(json.dumps({
            "token": token,
            "options": {"container_id": started_ubuntu_container["id"], "command": "ls /mnt"}
        }))
        _, msg = ws.recv_data()
        assert json.loads(msg.decode())["msg"] == "connected", msg

        data = ""
        ws.settimeout(30)
        for _ in range(60):
            try:
                _, msg = ws.recv_data()
            except Exception as e:
                print(e)
                break

            data += msg.decode("ascii", "ignore")

        assert data.replace("\x03", "").strip().split()[-1] == f"canary"
    finally:
        ws.close()


@pytest.fixture(scope="module")
def idmap_slice_1_container(ubuntu_image):
    # A container that uses idmap slice 2 to test idmap slice auto-allocation
    with container(ubuntu_image, {
        "name": "idmap_slice_1",
        "idmap": {"type": "ISOLATED", "slice": 1},
    }, True):
        yield


@pytest.mark.parametrize("target,config", [
    (0, None),
    (2147000001, {"type": "DEFAULT"}),
    (2147000001 + 65536, {"type": "ISOLATED", "slice": 1}),
    (2147000001 + 65536 * 2, {"type": "ISOLATED", "slice": None}),
])
def test_idmap(ubuntu_image, idmap_slice_1_container, target, config):
    with container(ubuntu_image, {
        "idmap": config,
    }, True) as c:
        assert ssh(f"ps -p {c['status']['pid']} -o uid,gid --no-headers").strip().split() == [
            str(target), str(target),
        ]

        mountpoint = get_mountpoint(c["dataset"])
        ssh(f"mkdir {mountpoint}/playground")
        ssh(nsenter(c, "touch /playground/canary"))
        assert ssh(f"stat -c '%u %g' {mountpoint}/playground/canary").strip().split() == ["0", "0"]


@pytest.mark.parametrize("configuration,has", [
    ({}, True),
    ({"capabilities_state": {"lease": False}}, False),
    ({"capabilities_policy": "ALLOW"}, True),
    ({"capabilities_policy": "ALLOW", "capabilities_state": {"lease": False}}, False),
    ({"capabilities_policy": "DENY", "capabilities_state": {**BASIC_CAPABILITIES}}, False),
    ({"capabilities_policy": "DENY", "capabilities_state": {**BASIC_CAPABILITIES, "lease": True}}, True),
])
def test_capabilities(ubuntu_image, configuration, has):
    with container(ubuntu_image, configuration, True, startup_script=textwrap.dedent("""\
        #!/bin/sh
        capsh --print
    """)) as c:
        s = script_output(c)

        if has:
            assert "cap_lease" in bounding_set(s)
        else:
            assert "cap_lease" not in bounding_set(s)

        def normalize(output):
            # `groups=0(root)` vs `groups=`
            return re.sub("groups=(.*)", "", output)

        # Ensure that the process launched with `nsenter` has the same capabilities as container init process
        assert normalize(ssh(nsenter(c, "capsh --print"))) == normalize(s)


def test_network(started_ubuntu_container):
    for i in itertools.count(1):
        try:
            assert ssh(nsenter(started_ubuntu_container, f"ping -c 1 {host().ip}"))
            assert ssh(nsenter(started_ubuntu_container, "ping -c 1 8.8.8.8"))
            assert "inet 10.47.214." in ssh(nsenter(started_ubuntu_container, "ip addr list"))
            assert "inet6 fd42:3656:7be9:e46c:" in ssh(nsenter(started_ubuntu_container, "ip addr list"))
            break
        except AssertionError:
            if i > 10:
                raise

            time.sleep(1)


def test_container_on_another_pool(ubuntu_image):
    with another_pool() as p:
        with container(ubuntu_image, {"pool": p["name"]}, True):
            pass


def test_incorrect_image(ubuntu_image):
    with pytest.raises(ValidationErrors) as ve:
        with container({**ubuntu_image, "name": ubuntu_image["name"] + "_"}):
            pass

    assert ve.value.errors[0].attribute == 'container_create.image.name'


def test_incorrect_image_version(ubuntu_image):
    with pytest.raises(ValidationErrors) as ve:
        with container({**ubuntu_image, "version": ubuntu_image["version"] + "_"}):
            pass

    assert ve.value.errors[0].attribute == 'container_create.image.version'
