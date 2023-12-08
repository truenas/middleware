import errno
import pytest

from middlewared.test.integration.utils import call, mock


def test_disable_mock_on_stable_release():
    with mock("system.is_stable", return_value=True):
        with pytest.raises(CallError) as ve:
            with mock("vmware.connect", return_value=None):
                pass

        assert ve.value.errno == errno.EPERM
