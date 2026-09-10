import subprocess
from unittest.mock import patch

import pytest

from middlewared.utils import git


@pytest.mark.parametrize(
    "stderr,returncode,reason",
    [
        (
            b"Cloning into '/mnt/.ix-apps/truenas_catalog'...\n"
            b"remote: Invalid username or token.\n"
            b"fatal: Authentication failed for 'https://github.com/truenas/apps/'\n",
            128,
            "fatal: Authentication failed for 'https://github.com/truenas/apps/'",
        ),
        (
            b"fatal: ambiguous argument 'origin/master': unknown revision or path not in the working tree.\n"
            b"Use '--' to separate paths from revisions, like this:\n"
            b"'git <command> [<revision>...] -- [<file>...]'\n",
            128,
            "fatal: ambiguous argument 'origin/master': unknown revision or path not in the working tree.",
        ),
        (
            b"error: Your local changes to the following files would be overwritten by merge:\n"
            b"\tix-dev/charts/plex/questions.yaml\n"
            b"Aborting\n",
            1,
            "error: Your local changes to the following files would be overwritten by merge:",
        ),
        (b"Some unprefixed failure\n", 1, "Some unprefixed failure"),
        (b"", -9, "git exited with code -9"),
    ],
)
@patch("middlewared.utils.git.logger")
def test__failure_names_the_cause(logger, stderr, returncode, reason):
    cp = subprocess.CompletedProcess(args=[], returncode=returncode, stdout=b"", stderr=stderr)

    expected = f"Failed to clone: {reason}. See /var/log/git.log for full git output"
    assert git._failure(cp, "Failed to clone").errmsg == expected
