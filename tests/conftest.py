import contextlib
import os

import pytest

from middlewared.test.integration.utils import call


@pytest.fixture(autouse=True, scope="function")
def log_test_name_to_middlewared_log(request):
    client_kwargs_list = [dict(host_ip=os.environ.get('controller1_ip', None))]
    if 'controller2_ip' in os.environ:
        client_kwargs_list.append(dict(host_ip=os.environ['controller2_ip']))

    for client_kwargs in client_kwargs_list:
        # Beware that this is executed after session/package/module/class fixtures are applied so the logs will still
        # not be exactly precise.
        with contextlib.suppress(Exception):
            call("test.notify_test_start", request.node.name, client_kwargs=client_kwargs)

    yield

    for client_kwargs in client_kwargs_list:
        # That's why we also notify test ends. What happens between a test end and the next test start is caused by
        # session/package/module/class fixtures setup code.
        with contextlib.suppress(Exception):
            call("test.notify_test_end", request.node.name, client_kwargs=client_kwargs)
