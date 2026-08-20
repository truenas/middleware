import subprocess
from unittest.mock import MagicMock, patch

import pytest

from middlewared.plugins.catalog.git_utils import pull_clone_repository
from middlewared.service import CallError
from middlewared.utils.git import checkout_repository, clone_repository, update_repo, validate_git_repo

REPOSITORY = "https://github.com/truenas/apps"
# Nothing is created here - `clone_repository` unconditionally removes its destination first
DESTINATION = "/var/empty/nonexistent-catalog-checkout"

HELPERS = [
    (clone_repository, (REPOSITORY, DESTINATION)),
    (checkout_repository, (DESTINATION, "master")),
    (update_repo, (DESTINATION, "master")),
    (validate_git_repo, (DESTINATION,)),
]


@pytest.mark.parametrize("helper, args", HELPERS)
def test_a_wedged_git_surfaces_as_a_call_error(helper, args):
    with patch("middlewared.utils.git.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 1)):
        with pytest.raises(CallError, match="Timed out"):
            helper(*args)


@pytest.mark.parametrize("helper, args", HELPERS)
def test_every_git_invocation_is_bounded(helper, args):
    with patch("middlewared.utils.git.subprocess.run", return_value=MagicMock(returncode=0)) as run:
        helper(*args)

    assert run.call_args_list
    for call in run.call_args_list:
        assert call.kwargs.get("timeout") is not None


def test_a_timed_out_update_still_falls_back_to_a_clone():
    with (
        patch("middlewared.plugins.catalog.git_utils.validate_git_repo", return_value=True),
        patch("middlewared.plugins.catalog.git_utils.checkout_repository"),
        patch(
            "middlewared.plugins.catalog.git_utils.update_repo",
            side_effect=CallError(f"Timed out after 600 seconds updating {DESTINATION!r} repository"),
        ),
        patch("middlewared.plugins.catalog.git_utils.clone_repository") as clone,
    ):
        assert pull_clone_repository(REPOSITORY, DESTINATION, "master") is True

    clone.assert_called_once_with(REPOSITORY, DESTINATION, "master", 1)
