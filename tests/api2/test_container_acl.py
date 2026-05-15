import contextlib
import shlex
from copy import deepcopy

import pytest

from middlewared.test.integration.assets.account import (
    group as account_group,
    user as account_user,
)
from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh

UBUNTU_IMAGE_NAME = "ubuntu:noble:amd64:default"


@pytest.fixture(scope="module", autouse=True)
def bridge():
    call(
        "lxc.update",
        {
            "v4_network": "10.47.214.0/24",
            "v6_network": "fd42:3656:7be9:e46c::0/64",
        },
    )


@pytest.fixture(scope="module")
def ubuntu_image():
    images = call("container.image.query_registry")
    version = [
        image["versions"][-1]["version"]
        for image in images
        if image["name"] == UBUNTU_IMAGE_NAME
    ][0]
    yield {"name": UBUNTU_IMAGE_NAME, "version": version}


def nsenter(container, command):
    return shlex.join(call("container.nsenter", container) + [command])


@contextlib.contextmanager
def _container(image, name="acltest", **options):
    c = call(
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
        yield c
    finally:
        if call("container.get_instance", c["id"])["status"]["state"] == "RUNNING":
            call("container.stop", c["id"], {"force": True}, job=True)
        call("container.delete", c["id"])


@pytest.fixture(scope="module")
def instance(ubuntu_image):
    with _container(ubuntu_image, name="acltest") as c:
        yield c


@pytest.fixture(scope="function")
def nfs4acl_dataset(instance):
    with account_group({"name": "testgrp"}) as g:
        with account_user(
            {
                "username": "testusr",
                "full_name": "testusr",
                "group": g["id"],
                "random_password": True,
            }
        ) as u:
            call("user.update", u["id"], {"userns_idmap": "DIRECT"})
            call("group.update", g["id"], {"userns_idmap": "DIRECT"})

            with dataset("virtnfsshare", {"share_type": "SMB"}) as ds:
                fs_device = call(
                    "container.device.create",
                    {
                        "container": instance["id"],
                        "attributes": {
                            "dtype": "FILESYSTEM",
                            "source": f"/mnt/{ds}",
                            "target": "/nfs4acl",
                        },
                    },
                )
                try:
                    call("container.start", instance["id"])
                    try:
                        yield {
                            "instance": call("container.get_instance", instance["id"]),
                            "user": u,
                            "group": g,
                            "dataset": ds,
                            "dev": "/nfs4acl",
                        }
                    finally:
                        call(
                            "container.stop", instance["id"], {"force": True}, job=True
                        )
                finally:
                    call("container.device.delete", fs_device["id"])


def create_container_users(c, uid, gid):
    """
    Create three test users inside the container.
    * `larry` has the specified UID.
    * `curly` has the specified GID as primary group.
    * `moe` has the specified GID as an auxiliary group.

    These all get evaluated differently based on ACL.

    NOTE: useradd -g <gid> requires the group to exist inside the container,
    so we groupadd it first.
    """
    ssh(nsenter(c, f"groupadd -g {gid} testgrp"))
    ssh(nsenter(c, f"useradd -u {uid} larry"))
    ssh(nsenter(c, f"useradd -g {gid} curly"))
    ssh(nsenter(c, f"useradd -G {gid} moe"))


def check_access(c, path, username, expected_access):
    account_string = f"sudo -i -u {username}"

    # READ and MODIFY should be able to list
    match expected_access:
        case "READ":
            ssh(nsenter(c, f"{account_string} ls {path}"))
            with pytest.raises(AssertionError, match="Operation not permitted"):
                ssh(nsenter(c, f"{account_string} mkdir {path}/testdir"))

            with pytest.raises(AssertionError, match="Operation not permitted"):
                ssh(nsenter(c, f"{account_string} chown {username} {path}"))

        case "MODIFY":
            ssh(nsenter(c, f"{account_string} ls {path}"))
            ssh(nsenter(c, f"{account_string} mkdir {path}/testdir"))
            ssh(nsenter(c, f"{account_string} rmdir {path}/testdir"))
            with pytest.raises(AssertionError, match="Operation not permitted"):
                ssh(nsenter(c, f"{account_string} chown {username} {path}"))

        case "FULL_CONTROL":
            ssh(nsenter(c, f"{account_string} chown {username} {path}"))

        case None:
            with pytest.raises(AssertionError, match="Operation not permitted"):
                ssh(nsenter(c, f"{account_string} ls {path}"))

            with pytest.raises(AssertionError, match="Operation not permitted"):
                ssh(nsenter(c, f"{account_string} mkdir {path}/testdir"))

            with pytest.raises(AssertionError, match="Operation not permitted"):
                ssh(nsenter(c, f"{account_string} chown {username} {path}"))
        case _:
            raise ValueError(f"{expected_access}: unexpected access string")


def test_container_nfs4acl_functional(nfs4acl_dataset):
    c = nfs4acl_dataset["instance"]
    create_container_users(
        c,
        nfs4acl_dataset["user"]["uid"],
        nfs4acl_dataset["group"]["gid"],
    )

    path = f"/mnt/{nfs4acl_dataset['dataset']}"
    acl_info = call("filesystem.getacl", path)
    assert acl_info["acltype"] == "NFS4"
    acl = deepcopy(acl_info["acl"])
    acl.extend(
        [
            {
                "tag": "GROUP",
                "type": "ALLOW",
                "perms": {"BASIC": "READ"},
                "flags": {"BASIC": "INHERIT"},
                "id": nfs4acl_dataset["group"]["gid"],
            },
            {
                "tag": "USER",
                "type": "ALLOW",
                "perms": {"BASIC": "READ"},
                "flags": {"BASIC": "INHERIT"},
                "id": nfs4acl_dataset["user"]["uid"],
            },
        ]
    )

    for username in ("larry", "curly", "moe"):
        check_access(c, nfs4acl_dataset["dev"], username, None)

    # set READ ACL
    call("filesystem.setacl", {"path": path, "dacl": acl}, job=True)

    ssh(f"cp /bin/nfs4xdr_getfacl {path}/nfs4xdr_getfacl")
    ssh(f"cp /bin/nfs4xdr_setfacl {path}/nfs4xdr_setfacl")

    # FIXME - NAS-134466
    """
    ssh(f'cp /bin/nfs4xdr_getfacl /mnt/{ds}/nfs4xdr_getfacl')

    cmd = [
        'incus', 'exec', '-T', instance['name'],
        '-- bash -c "/host/nfs4xdr_getfacl -j /host"'
    ]
    instance_acl = json.loads(ssh(' '.join(cmd)))

    # Check that the ids in the ACL have been mapped
    check_nfs4_acl_entry(
        instance_acl['acl'],
        nfs4acl_dataset['group']['gid'],
        'ALLOW',
        'GROUP',
        {'BASIC': 'READ'},
        {'BASIC': 'INHERIT'}
    )

    check_nfs4_acl_entry(
        instance_acl['acl'],
        instance['user']['uid'],
        'ALLOW',
        'USER',
        {'BASIC': 'READ'},
        {'BASIC': 'INHERIT'}
    )
    """

    for username in ("larry", "curly", "moe"):
        check_access(c, nfs4acl_dataset["dev"], username, "READ")

    acl = deepcopy(acl_info["acl"])
    acl.extend(
        [
            {
                "tag": "GROUP",
                "type": "ALLOW",
                "perms": {"BASIC": "MODIFY"},
                "flags": {"BASIC": "INHERIT"},
                "id": nfs4acl_dataset["group"]["gid"],
            },
            {
                "tag": "USER",
                "type": "ALLOW",
                "perms": {"BASIC": "MODIFY"},
                "flags": {"BASIC": "INHERIT"},
                "id": nfs4acl_dataset["user"]["uid"],
            },
        ]
    )

    # set MODIFY ACL
    call("filesystem.setacl", {"path": path, "dacl": acl}, job=True)

    for username in ("larry", "curly", "moe"):
        check_access(c, nfs4acl_dataset["dev"], username, "MODIFY")

    acl = deepcopy(acl_info["acl"])
    acl.extend(
        [
            {
                "tag": "GROUP",
                "type": "ALLOW",
                "perms": {"BASIC": "FULL_CONTROL"},
                "flags": {"BASIC": "INHERIT"},
                "id": nfs4acl_dataset["group"]["gid"],
            },
            {
                "tag": "USER",
                "type": "ALLOW",
                "perms": {"BASIC": "FULL_CONTROL"},
                "flags": {"BASIC": "INHERIT"},
                "id": nfs4acl_dataset["user"]["uid"],
            },
        ]
    )

    # set FULL_CONTROL ACL
    call("filesystem.setacl", {"path": path, "dacl": acl}, job=True)

    for username in ("larry", "curly", "moe"):
        check_access(c, nfs4acl_dataset["dev"], username, "FULL_CONTROL")
