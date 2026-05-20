import base64
import contextlib
import shlex
import textwrap

from middlewared.test.integration.utils import call, pool, ssh

UBUNTU_IMAGE_NAME = "ubuntu:noble:amd64:default"
ALPINE_IMAGE_NAME = "alpine:edge:amd64:default"
VIRSH = "virsh -c 'lxc:///system?socket=/run/truenas_libvirt/libvirt-sock'"


def nsenter(container, command):
    return shlex.join(call("container.nsenter", container) + [command])


def resolve_image(name):
    images = call("container.image.query_registry")
    version = [image["versions"][-1]["version"] for image in images if image["name"] == name][0]
    return {"name": name, "version": version}


def configure_bridge():
    call(
        "lxc.update",
        {
            "v4_network": "10.47.214.0/24",
            "v6_network": "fd42:3656:7be9:e46c::0/64",
        },
    )


def get_mountpoint(dataset):
    rv = call("zfs.resource.query", {"paths": [dataset], "properties": ["mountpoint"]})
    return rv[0]["properties"]["mountpoint"]["value"]


@contextlib.contextmanager
def container(image, options=None, start=False, startup_script=None, name="test"):
    options = options or {}

    container = call(
        "container.create",
        {
            "name": name,
            "pool": pool,
            "image": image,
            **options,
        },
        job=True,
    )
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
                base64.b64encode(
                    textwrap.dedent("""\
                    #!/bin/sh
                    /script.sh > /.log 2>&1
                    mv /.log /log
                """).encode("ascii")
                ).decode("ascii"),
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
        if call("container.get_instance", container["id"])["status"]["state"] == "RUNNING":
            call("container.stop", container["id"], {"force": True}, job=True)
        call("container.delete", container["id"])

        #  Id   Name   State
        # --------------------
        assert container["uuid"] not in ssh(f"{VIRSH} list --all")


@contextlib.contextmanager
def filesystem_device(container_id, source, target):
    """Attach a FILESYSTEM device for the lifetime of the block.

    container.device.delete requires the container to be STOPPED, so on exit
    we force-stop the container (if still present and running) before deleting
    the device. If the container was deleted by an outer context manager
    already, we silently skip cleanup.
    """
    device = call(
        "container.device.create",
        {
            "container": container_id,
            "attributes": {
                "dtype": "FILESYSTEM",
                "source": source,
                "target": target,
            },
        },
    )
    try:
        yield device
    finally:
        try:
            instance = call("container.get_instance", container_id)
        except Exception:
            return
        if instance["status"]["state"] == "RUNNING":
            call("container.stop", container_id, {"force": True}, job=True)
        call("container.device.delete", device["id"])
