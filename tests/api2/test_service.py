import time

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


def test_non_silent_service_start_failure():
    # Starting UPS service with invalid configuration will fail, let's use this to our advantage to test
    # service startup failure error reporting.
    call("service.stop", "ups")
    call("datastore.update", "services.ups", 1, {"ups_monuser": ""})

    with pytest.raises(CallError) as e:
        call("service.start", "ups", {"silent": False})

    lines = e.value.errmsg.splitlines()
    first_entry_timestamp = " ".join(lines[0].split()[:3])
    first_length = len(lines)
    assert any("upsmon[" in line for line in lines), lines
    assert any("systemd[" in line for line in lines), lines

    time.sleep(5)

    with pytest.raises(CallError) as e:
        call("service.start", "ups", {"silent": False})

    lines = e.value.errmsg.splitlines()
    assert len(lines) == first_length  # Same error messages
    assert " ".join(lines[0].split()[:3]) != first_entry_timestamp  # But with a different timestamp
