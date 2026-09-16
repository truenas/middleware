"""Assets for the TrueNAS S3 service: accounts, keys, buckets, grants.

The S3 service is two things a test has to arrange separately. An
**access key** is the SigV4 credential pair a client signs with; it
belongs to a TrueNAS account and the service runs that key's requests
as the account. A **bucket** is a ZFS dataset `sharing.s3.create` makes
and registers, carrying the grants that say which accounts reach it and
how. Neither is reachable over the wire: `CreateBucket` is refused
unless the key carries `manage_buckets`, and even then the daemon asks
middleware to do it. So a protocol test provisions through here and
drives through a client.

**Provisioning only, and deliberately.** Everything in this module is
the middleware API and the standard library, so it stays importable on
a runner that has no S3 client library at all. The client stack — the
boto3 client, the helpers that read an answer off it, the request
shapes botocore will not construct — is `tests/protocols/s3_proto.py`,
beside `nfs_proto` and `smb_proto`.
"""

import contextlib
import time
from types import SimpleNamespace
from typing import Any

from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server

__all__ = [
    "DEFAULT_S3_PORT",
    "S3_SERVICE",
    "everyone_grant",
    "group_grant",
    "s3_access_key",
    "s3_account",
    "s3_bucket",
    "s3_endpoint",
    "s3_pids",
    "s3_service",
    "s3_started",
    "user_grant",
    "wait_for_listener",
]

S3_SERVICE = "s3"
"""The service name `service.control` takes for the S3 service."""

DEFAULT_S3_PORT = 9000
"""Where the daemon listens when the configuration names no listener."""


# ── the service ──────────────────────────────────────────────────────


def s3_started() -> bool:
    return call("service.query", [["service", "=", S3_SERVICE]], {"get": True})["state"] == "RUNNING"


def s3_pids() -> list[int]:
    """The service's pids, which say whether a change reloaded or restarted it."""
    return call("service.query", [["service", "=", S3_SERVICE]], {"get": True})["pids"]


@contextlib.contextmanager
def s3_service(config: dict[str, Any] | None = None):
    """Run the S3 service for the block, restoring what was displaced.

    `config` is applied through `s3.update` before the service starts and
    put back afterwards, so a suite that needs a listener or a region of
    its own does not have to restore it by hand.
    """
    old = None
    if config:
        current = call("s3.config")
        old = {key: current[key] for key in config}
        call("s3.update", config)

    was_running = s3_started()
    if not was_running:
        assert call("service.control", "START", S3_SERVICE, {"silent": False}, job=True)
    try:
        yield
    finally:
        if not was_running:
            call("service.control", "STOP", S3_SERVICE, {"silent": False}, job=True)
        if old is not None:
            call("s3.update", old)


def s3_endpoint(port: int = DEFAULT_S3_PORT, tls: bool = False) -> str:
    """Where the S3 service answers, from the server under test.

    The server's own address rather than loopback: the tests run on the
    runner and the daemon runs on the appliance.
    """
    scheme = "https" if tls else "http"
    return f"{scheme}://{truenas_server.ip}:{port}"


def wait_for_listener(port: int = DEFAULT_S3_PORT, timeout: float = 60.0) -> None:
    """Block until the daemon accepts a connection on `port`.

    A fresh bucket costs the daemon a registration before it listens, so
    a client built the moment `service.control` returns can beat it to
    the socket. Failing here rather than in the first test is what makes
    that legible.
    """
    import socket

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((truenas_server.ip, port)) == 0:
                return
        time.sleep(0.5)
    raise AssertionError(f"the S3 service never listened on {truenas_server.ip}:{port}")


# ── accounts and their keys ──────────────────────────────────────────


@contextlib.contextmanager
def s3_access_key(username: str, *, name: str | None = None, **kwargs):
    """One access key for an existing account.

    `manage_buckets=True` needs the account to hold `SHARING_S3_WRITE`;
    `s3_account` is what arranges that. The entry carries its secret,
    which is what a client signs with.
    """
    key = call("s3.accesskey.create", {"name": name or f"{username} key", "username": username, **kwargs})
    try:
        yield key
    finally:
        try:
            call("s3.accesskey.delete", key["id"])
        except InstanceNotFound:
            pass


@contextlib.contextmanager
def s3_account(username: str, *, manage_buckets: bool = False, roles: list[str] | None = None, keys: int = 1, **kwargs):
    """An account that can sign S3 requests, and its keys.

    Yields a namespace carrying `username`, `uid`, `gid` and `keys` —
    the access-key entries, `keys[0]` being the one most callers want.

    **`manage_buckets` is the account's role and the key's flag, and
    both are needed.** The flag lets a key ask middleware to create and
    delete buckets, and middleware answers as the account, so
    `s3.accesskey.create` refuses the flag for an account without
    `SHARING_S3_WRITE`. Asking for it here grants the role through a
    privilege on the account's own group and takes it away again.

    Only the *first* key carries the flag. That is deliberate: the flag
    scopes a key rather than an account, and a suite proving so needs
    two keys on one account that differ in nothing else.
    """
    wanted = list(roles or [])
    if manage_buckets and "SHARING_S3_WRITE" not in wanted:
        wanted.append("SHARING_S3_WRITE")

    with create_user(
        {
            "username": username,
            "full_name": username,
            "group_create": True,
            "password": "test1234",
            **kwargs,
        }
    ) as account:
        with contextlib.ExitStack() as stack:
            if wanted:
                stack.enter_context(
                    privilege(
                        {
                            "name": f"{username} S3 privilege",
                            "local_groups": [account["group"]["bsdgrp_gid"]],
                            "ds_groups": [],
                            "roles": wanted,
                            "web_shell": False,
                        }
                    )
                )
            made = [
                stack.enter_context(
                    s3_access_key(
                        username,
                        name=f"{username} key {n}",
                        **({"manage_buckets": True} if manage_buckets and n == 0 else {}),
                    )
                )
                for n in range(keys)
            ]
            yield SimpleNamespace(
                username=username,
                uid=account["uid"],
                gid=account["group"]["bsdgrp_gid"],
                user=account,
                keys=made,
                key=made[0],
            )


# ── grants ───────────────────────────────────────────────────────────


def user_grant(uid: int, access: str = "READWRITE") -> dict[str, Any]:
    """A grant naming one account by uid."""
    return {"principal_type": "USER", "xid": uid, "access": access}


def group_grant(gid: int, access: str = "READWRITE") -> dict[str, Any]:
    """A grant naming one group by gid."""
    return {"principal_type": "GROUP", "xid": gid, "access": access}


def everyone_grant(access: str = "READONLY") -> dict[str, Any]:
    """A grant naming every account holding a valid access key."""
    return {"principal_type": "EVERYONE", "access": access}


# ── buckets ──────────────────────────────────────────────────────────


@contextlib.contextmanager
def s3_bucket(name: str, *, keep_dataset: bool = False, **kwargs):
    """A bucket, and the dataset it is, for the block.

    Every field of `sharing.s3.create` may be given: `owner`, `grants`,
    `object_ownership`, `permissions_model`, `versioning`,
    `object_lock`, `snapshot_versions`, `multipart_etag`, `audit`, and
    `dataset` when the caller wants to place it itself.

    **The dataset goes on the way out, which `sharing.s3.delete` does
    not do.** Deregistering a bucket deliberately keeps its objects, so
    a fixture that only deleted the share would leave the next run's
    dataset name taken and its objects underneath. `keep_dataset` is for
    the tests that are about exactly that.
    """
    entry = call("sharing.s3.create", {"name": name, **kwargs})
    try:
        yield entry
    finally:
        with contextlib.suppress(Exception):
            call("sharing.s3.delete", entry["id"])
        if not keep_dataset:
            with contextlib.suppress(Exception):
                call("zfs.resource.destroy", {"path": entry["dataset"], "recursive": True})
