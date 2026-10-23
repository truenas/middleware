import errno

import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.utils import client

NONEXISTENT_USER_ID = 999999999


@pytest.fixture()
def token_session():
    with client() as origin:
        token = origin.call("auth.generate_token", 300, {}, True)
        with client(auth=None) as session:
            assert session.call("auth.login_with_token", token)
            yield origin, session


def authorized_for_write(session):
    """Probe a role-gated write method without changing state. The method body always
    raises, so only the 'Not authorized' signature distinguishes a rejected call."""
    with pytest.raises(Exception) as exc:
        session.call("user.update", NONEXISTENT_USER_ID, {})

    return not (
        isinstance(exc.value, CallError) and exc.value.errno == errno.EACCES and exc.value.errmsg == "Not authorized"
    )


def test_become_readonly_blocks_writes_for_direct_session():
    with client() as session:
        session.call("privilege.become_readonly")

        assert not authorized_for_write(session)


def test_become_readonly_blocks_writes_for_token_session(token_session):
    _, session = token_session

    session.call("privilege.become_readonly")

    assert not authorized_for_write(session)


def test_become_readonly_reduces_token_session_privilege(token_session):
    _, session = token_session

    session.call("privilege.become_readonly")

    privilege = session.call("auth.me")["privilege"]
    assert "FULL_ADMIN" not in privilege["roles"]
    assert privilege["web_shell"] is False


def test_become_readonly_redacts_for_token_session(token_session):
    _, session = token_session

    session.call("privilege.become_readonly")

    user = session.call("user.query", [["username", "=", "root"]], {"get": True})
    assert user["unixhash"] == "********"


def test_become_readonly_on_token_keeps_originating_session_privilege(token_session):
    origin, session = token_session
    assert "FULL_ADMIN" in origin.call("auth.me")["privilege"]["roles"]

    session.call("privilege.become_readonly")

    privilege = origin.call("auth.me")["privilege"]
    assert "FULL_ADMIN" in privilege["roles"]
    assert privilege["web_shell"] is True


def test_become_readonly_on_token_keeps_originating_session_writable(token_session):
    origin, session = token_session

    session.call("privilege.become_readonly")

    assert authorized_for_write(origin)
