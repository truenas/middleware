"""
Spotlight searches through SMB, as a Mac sends them. mdsearch, the Spotlight client of Samba, runs on the test runner
and connects to the server. TrueSearch answers the searches.
"""

import os
import subprocess
import time

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.client import truenas_server

SHARE_NAME = "SPOTLIGHT"
USERNAME = "spotuser"
PASSWORD = "Spot1234$"


@pytest.fixture(scope="module")
def spotlight_share():
    # truesearchd and truesearch-indexer each ask middleware for the entitlement when they start.
    with mock("truesearch.unavailable_reasons", return_value=[]), entitled("TRUESEARCH"):
        protocols = call("smb.config")["search_protocols"]
        call("smb.update", {"search_protocols": ["SPOTLIGHT"]})
        try:
            with dataset("spotlight_test", data={"share_type": "SMB"}) as ds:
                path = os.path.join("/mnt", ds)
                ssh(f"mkdir {path}/Reports {path}/private")
                ssh(f"touch {path}/Reports/report_q3.pdf {path}/Reports/UPPER.PDF {path}/private/report_private.txt")
                # Only root can enter the private directory.
                call(
                    "filesystem.setperm",
                    {"path": f"{path}/private", "mode": "700", "options": {"stripacl": True}},
                    job=True,
                )
                with user(
                    {
                        "username": USERNAME,
                        "full_name": USERNAME,
                        "group_create": True,
                        "password": PASSWORD,
                    }
                ):
                    with smb_share(path, SHARE_NAME):
                        yield path
        finally:
            call("smb.update", {"search_protocols": protocols})


def mdsearch(query: str, *options: str) -> subprocess.CompletedProcess:
    """Send a Spotlight query to the share as the test user. Each line of the output is a path in the share."""
    return subprocess.run(
        ["mdsearch", "-U", f"{USERNAME}%{PASSWORD}", *options, truenas_server.ip, SHARE_NAME, query],
        capture_output=True,
        text=True,
        timeout=120,
    )


def expect(query: str, expected: list[str], *options: str) -> None:
    """Wait until the search finds the expected paths. TrueSearch indexes a new share in the background."""
    for i in range(12):
        result = mdsearch(query, *options)
        if result.returncode == 0 and sorted(result.stdout.splitlines()) == sorted(expected):
            return

        time.sleep(5)

    assert False, (result.returncode, result.stdout, result.stderr)


def test_a_name_is_found(spotlight_share):
    expect('kMDItemFSName=="report_q3.pdf"', ["Reports/report_q3.pdf"])


def test_case_folds_only_with_c(spotlight_share):
    expect('kMDItemFSName=="upper.pdf"c', ["Reports/UPPER.PDF"])

    result = mdsearch('kMDItemFSName=="upper.pdf"')
    assert (result.returncode, result.stdout) == (0, ""), result


def test_a_scope_is_relative_to_the_share(spotlight_share):
    expect('kMDItemFSName=="report*"cd', ["Reports/report_q3.pdf"], "-p", "Reports")


def test_the_user_does_not_find_what_the_user_cannot_open(spotlight_share):
    # The search ignores case. Thus the folder Reports is a hit too.
    expect('kMDItemFSName=="report*"cd', ["Reports", "Reports/report_q3.pdf"])

    # The private file is in the index. A search as root finds it.
    found = call(
        "truesearch.query",
        {
            "path": spotlight_share,
            "query-filters": [["name", "=", "report_private.txt"]],
        },
    )
    assert [entry["path"] for entry in found] == [f"{spotlight_share}/private/report_private.txt"]


def test_spotlight_is_off_without_the_search_protocol(spotlight_share):
    expect('kMDItemFSName=="report_q3.pdf"', ["Reports/report_q3.pdf"])

    call("smb.update", {"search_protocols": []})
    try:
        result = mdsearch('kMDItemFSName=="report_q3.pdf"')
        assert result.returncode != 0 or result.stdout == "", result
    finally:
        call("smb.update", {"search_protocols": ["SPOTLIGHT"]})
