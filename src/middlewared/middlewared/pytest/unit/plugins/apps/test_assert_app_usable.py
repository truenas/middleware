import unittest.mock

import pytest

from middlewared.plugins.apps.utils import app_version, assert_app_usable
from middlewared.service import CallError


def app(state, **kwargs):
    return unittest.mock.Mock(id="actual-budget", state=state, **kwargs)


@pytest.mark.parametrize("state", ["CRASHED", "DEPLOYING", "RUNNING", "STOPPED", "STOPPING"])
def test_usable_states_are_allowed(state):
    assert_app_usable(app(state))


def test_error_state_is_refused():
    with pytest.raises(CallError) as exc_info:
        assert_app_usable(app("ERROR", error_reason="METADATA_UNREADABLE"))

    # The reason belongs in the message, it is the only clue as to what to look at on disk
    assert "METADATA_UNREADABLE" in str(exc_info.value)
    assert "actual-budget" in str(exc_info.value)


def test_app_version_returns_the_version():
    assert app_version(app("RUNNING", version="1.1.13")) == "1.1.13"


def test_app_version_refuses_an_app_without_one():
    # Reaching this means an operation is missing its `assert_app_usable` call
    with pytest.raises(AssertionError):
        app_version(app("ERROR", version=None))
