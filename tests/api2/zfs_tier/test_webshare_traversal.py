"""WebShare `no_dataset_traversal`, which follows `zfs.tier.config.enabled`.

The WebShare counterpart of the SMB `shadow:no_dataset_traversal` coverage in
test_shares.py. Tiering makes the tier contract authoritative for what a share
exposes, so a share root must stop at a child dataset.

These tests need no SPECIAL vdev: `no_dataset_traversal` follows the global
tiering switch alone, so they run on the boot pool and skip the `tier_pool`
fixture.
"""

import contextlib
import json

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.webshare import (
    WebshareError,
    webshare_server,
    webshare_session,
    webshare_share,
)
from middlewared.test.integration.utils import call, poll, ssh

USERNAME = "webshare_tier"
PASSWORD = "password"
SHARE_NAME = "Tiered"
CHILD = "child"
PARENT_FILE = "parent.txt"
INVALID_PARAMS = -32602


@contextlib.contextmanager
def tiering(enabled):
    original = call("zfs.tier.config")["enabled"]
    call("zfs.tier.update", {"enabled": enabled})
    try:
        yield
    finally:
        call("zfs.tier.update", {"enabled": original})


@pytest.fixture(scope="module")
def share():
    """A WebShare share whose root holds one file and one child dataset."""
    with entitled("WEBSHARE"), entitled("ZFSTIER"):
        with webshare_server():
            with dataset("webshare_tier") as ds:
                call("pool.dataset.create", {"name": f"{ds}/{CHILD}"})
                with user({
                    "username": USERNAME,
                    "full_name": USERNAME,
                    "group_create": True,
                    "password": PASSWORD,
                    "webshare": True,
                }) as u:
                    ssh(f"touch /mnt/{ds}/{PARENT_FILE}")
                    ssh(f"chown -R {u['uid']}:{u['group']['bsdgrp_gid']} /mnt/{ds}")
                    with webshare_share(f"/mnt/{ds}", SHARE_NAME):
                        yield ds

                    poll(
                        lambda: call("pool.dataset.processes", ds),
                        condition=lambda processes: not processes,
                        timeout=30,
                        message=f"{ds}: Webshare still holds the dataset",
                    )


def _webshare_config():
    return json.loads(ssh("cat /etc/webshare/config.json"))


def _share_root(session):
    return session.shares()[SHARE_NAME]["fileHandle"]


@pytest.mark.parametrize("enabled", [True, False])
def test_config_no_dataset_traversal_follows_tiering(share, enabled):
    """`zfs.tier.update` renders the new value before it returns, as it waits for the WebShare reload."""
    with tiering(enabled):
        assert _webshare_config()["no_dataset_traversal"] is enabled


def test_child_dataset_is_refused_while_tiering_enabled(share):
    with tiering(True):
        # A session keeps the configuration it started with, so this one starts after the update.
        with webshare_session(USERNAME, PASSWORD) as session:
            with pytest.raises(WebshareError) as ve:
                session.call("directory.getHandle", {"path": f"/{SHARE_NAME}/{CHILD}"})

            assert ve.value.code == INVALID_PARAMS
            assert ve.value.data["reason"] == "dataset_boundary"


def test_child_dataset_is_left_out_of_the_share_root_while_tiering_enabled(share):
    with tiering(True):
        with webshare_session(USERNAME, PASSWORD) as session:
            items = session.listdir(f"/{SHARE_NAME}", _share_root(session))

            assert {item["name"] for item in items} == {PARENT_FILE}


def test_child_dataset_is_reachable_while_tiering_disabled(share):
    with tiering(False):
        with webshare_session(USERNAME, PASSWORD) as session:
            items = session.listdir(f"/{SHARE_NAME}", _share_root(session))
            assert {item["name"] for item in items} == {PARENT_FILE, CHILD}

            handle = session.call("directory.getHandle", {"path": f"/{SHARE_NAME}/{CHILD}"})
            assert handle["isDir"] is True
