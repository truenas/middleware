import os
import pytest

from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.pytest import failed

# pytest fixtures
# Importing pytest fixtures in test modules is not supported.
# The work-around is to import them in conftest.py (this module),
# making them available (in scope) for all test modules.
# See: https://stackoverflow.com/questions/75647682/how-can-i-resolve-flake8-unused-import-error-for-pytest-fixture-imported-from
from middlewared.test.integration.assets.roles import unprivileged_user_fixture  # noqa
from middlewared.test.integration.assets.account import test_user  # noqa

pytest.register_assert_rewrite("middlewared.test")


@pytest.fixture(autouse=True)
def fail_fixture():
    # We need to flag test as having failed
    if failed[0] is not None:
        pytest.exit(failed[0], pytest.ExitCode.TESTS_FAILED)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    # This is called after test run is finished, right before returning
    # exit to the system. At this point we introduce a custom error code
    # to indicate to jenkins that the junit results shouldn't be trusted
    # due to an early abort of the run (but we still want to present to
    # developer
    if failed[0] is not None:
        session.exitstatus = os.EX_SOFTWARE


@pytest.fixture(autouse=True)
def log_test_name_to_middlewared_log(request):
    # Beware that this is executed after session/package/module/class fixtures
    # are applied so the logs will still not be exactly precise.
    test_name = request.node.name
    truenas_server.client.call("test.notify_test_start", test_name)
    yield

    # That's why we also notify test ends. What happens between a test end
    # and the next test start is caused by session/package/module/class
    # fixtures setup code.
    truenas_server.client.call("test.notify_test_end", test_name)


@pytest.fixture(autouse=True)
def mock_role():
    truenas_server.client.call("test.add_mock_role")
    yield
