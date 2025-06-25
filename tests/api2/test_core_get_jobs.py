import pytest

from truenas_api_client import ValidationErrors

from middlewared.test.integration.utils import call


def test_does_not_crash_when_too_many_arguments():
    with pytest.raises(ValidationErrors) as ve:
        call("rsynctask.run", 1, 2, job=True)

    assert str(ve.value) == "[EINVAL] ALL: Too many arguments (expected 1, found 2)"

    call("core.get_jobs")
