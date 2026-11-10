"""WebShare stops at child datasets while tiering is enabled.

Middleware renders `no_dataset_traversal` in /etc/webshare/config.json from
`zfs.tier.config.enabled` and reloads WebShare when tiering is toggled. A
WebShare session keeps the configuration it started with, so every check opens
a new session.
"""

import functools
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
from middlewared.test.integration.utils import call, enterprise_test, poll, ssh

pytestmark = enterprise_test

USERNAME = "tier_webshare"
PASSWORD = "password"
SHARE_NAME = "TierShare"


@pytest.fixture(scope="module")
def share(tier_pool):
    """A share on the tier pool with a child dataset `nested` mounted inside it."""
    with entitled("WEBSHARE"):
        with webshare_server():
            with dataset("webshare_tier", pool=tier_pool["name"]) as ds:
                with dataset("webshare_tier/nested", pool=tier_pool["name"]) as nested:
                    with user(
                        {
                            "username": USERNAME,
                            "full_name": USERNAME,
                            "group_create": True,
                            "password": PASSWORD,
                            "webshare": True,
                        }
                    ) as u:
                        ssh(f"echo Share > /mnt/{ds}/file.txt")
                        ssh(f"echo Nested > /mnt/{nested}/x")
                        ssh(f"chown -R {u['uid']}:{u['group']['bsdgrp_gid']} /mnt/{ds}")

                        with webshare_share(f"/mnt/{ds}", SHARE_NAME):
                            yield ds

                        for held in (nested, ds):
                            poll(
                                functools.partial(call, "pool.dataset.processes", held),
                                condition=lambda processes: not processes,
                                timeout=30,
                                message=f"{held}: Webshare still holds the dataset",
                            )


def _no_dataset_traversal():
    return json.loads(ssh("cat /etc/webshare/config.json"))["no_dataset_traversal"]


def _list_share_and_get_nested_handle():
    with webshare_session(USERNAME, PASSWORD) as session:
        handle = session.shares()[SHARE_NAME]["fileHandle"]
        names = session.list_directory(f"/{SHARE_NAME}", handle)
        try:
            nested = session.call("directory.getHandle", {"path": f"/{SHARE_NAME}/nested"})
        except WebshareError as e:
            nested = e

        return names, nested


def test_config_rendered_when_tiering_disabled(share, disabled_tier):
    assert _no_dataset_traversal() is False


def test_config_rendered_when_tiering_enabled(share):
    assert _no_dataset_traversal() is True


def test_child_dataset_reachable_without_tiering(share, disabled_tier):
    names, nested = _list_share_and_get_nested_handle()

    assert "file.txt" in names
    assert "nested" in names
    assert not isinstance(nested, WebshareError), nested
    assert nested["fileHandle"]


def test_child_dataset_hidden_and_refused_with_tiering(share):
    names, nested = _list_share_and_get_nested_handle()

    assert "file.txt" in names
    assert "nested" not in names
    assert isinstance(nested, WebshareError), nested
    assert nested.data["reason"] == "dataset_boundary"
