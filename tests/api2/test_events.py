import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import client


def test_can_subscribe_to_failover_status_event_without_authorization():
    with client(auth=None) as c:
        c.subscribe("failover.status", lambda *args, **kwargs: None)


def test_can_not_subscribe_to_an_event_without_authorization():
    with client(auth=None) as c:
        with pytest.raises(CallError) as ve:
            c.subscribe("core.get_jobs", lambda *args, **kwargs: None)

        assert ve.value.errno == errno.EACCES
