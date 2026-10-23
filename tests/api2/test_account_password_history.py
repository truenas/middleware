import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.product import set_fips_available
from middlewared.test.integration.utils import call
from middlewared.utils.security import MAX_PASSWORD_HISTORY

TEST_HISTORY = 5  # validate 5 generations of passwords
USERNAME = "historypwduser"
PASSWORD = "Canary"
REUSE_ERROR = "requires a password that does not match"


@pytest.fixture(scope="module")
def password_history():
    with set_fips_available(True):
        call("system.security.update", {"password_history_length": TEST_HISTORY}, job=True)
        try:
            yield
        finally:
            # Must be restored before the mock unwinds, otherwise the update is rejected
            call("system.security.update", {"password_history_length": None}, job=True)


@pytest.fixture(scope="function")
def history_user(password_history):
    with user(
        {
            "username": USERNAME,
            "full_name": USERNAME,
            "group_create": True,
            "password": PASSWORD,
        }
    ) as u:
        yield u


def test_set_password_stores_usable_history(history_user):
    """Password history written by user.set_password must be readable back"""
    for i in range(0, TEST_HISTORY):
        call("user.set_password", {"username": USERNAME, "new_password": f"Canary{i}"})

    stored = call("user.get_instance", history_user["id"])["password_history"]
    assert len(stored) == TEST_HISTORY, str(stored)

    for i in range(0, TEST_HISTORY):
        with pytest.raises(ValidationErrors, match=REUSE_ERROR):
            call("user.set_password", {"username": USERNAME, "new_password": f"Canary{i}"})

    # We've cycled through history and should be OK again
    call("user.set_password", {"username": USERNAME, "new_password": PASSWORD})


def test_set_password_history_maximum(history_user):
    """user.set_password must discard hashes beyond the maximum history length"""
    for i in range(0, MAX_PASSWORD_HISTORY + 2):
        call("user.set_password", {"username": USERNAME, "new_password": f"Canary{i}"})

    stored = call("user.get_instance", history_user["id"])["password_history"]
    assert len(stored) == MAX_PASSWORD_HISTORY, str(stored)
