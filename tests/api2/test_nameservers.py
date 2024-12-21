from contextlib import contextmanager

import pytest

from middlewared.test.integration.utils import call
from middlewared.service_exception import ValidationErrors


@contextmanager
def revert_nameservers():
    to_revert = call("network.general.summary")["nameservers"]
    payload = dict()
    for idx, i in enumerate(to_revert, start=1):
        payload[f"nameserver{idx}"] = i

    try:
        yield
    finally:
        call("network.configuration.update", payload)


def test_invalid_nameserver():
    with revert_nameservers():
        with pytest.raises(
            ValidationErrors, match="Loopback is not a valid nameserver"
        ):
            call("network.configuration.update", {"nameserver1": "127.0.0.1"})
