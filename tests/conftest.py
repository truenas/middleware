import pytest

from middlewared.test.integration.assets.roles import unprivileged_user_fixture  # noqa
from middlewared.test.integration.utils.client import client, truenas_server
from middlewared.test.integration.utils.pytest import failed

pytest.register_assert_rewrite("middlewared.test")


@pytest.fixture(autouse=True)
def fail_fixture():
    if failed[0] is not None:
        pytest.exit(failed[0], 1)


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
