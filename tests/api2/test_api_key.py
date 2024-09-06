import pytest

from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.account import user as temp_user
from middlewared.test.integration.utils.client import truenas_server


@pytest.fixture(scope="module")
def tuser():
    with temp_user(
        {
            "username": "testuser",
            "full_name": "Test User",
            "group_create": True,
            "password": "test1234",
        }
    ) as u:
        yield u


def test_root_api_key_websocket(tuser):
    """We should be able to call a method with root API key using Websocket."""
    ip = truenas_server.ip
    with api_key([{"method": "*", "resource": "*"}]) as key:
        results = ssh(
            f"sudo -u {tuser["username"]} midclt -u ws://{ip}/api/current --api-key {key} call system.info",
            completes_response=True,
        )
        assert results["result"] is True, results["output"]
        assert "uptime" in results["stdout"]
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key)
            # root-level API key should be able to start / stop services
            c.call("service.start", "cifs")
            c.call("service.stop", "cifs")
            # root-level API key should be able to enable / disable services
            c.call("service.update", "cifs", {"enable": True})
            c.call("service.update", "cifs", {"enable": False})


def test_allowed_api_key_websocket(tuser):
    """We should be able to call a method with API key that allows that call using Websocket."""
    ip = truenas_server.ip
    with api_key([{"method": "CALL", "resource": "system.info"}]) as key:
        results = ssh(
            f"sudo -u {tuser["username"]} midclt -u ws://{ip}/api/current --api-key {key} call system.info",
            completes_response=True,
        )
        assert results["result"] is True, results["output"]
        assert "uptime" in results["stdout"]


def test_denied_api_key_websocket(tuser):
    """We should not be able to call a method with API key that does not allow that call using Websocket."""
    ip = truenas_server.ip
    with api_key([{"method": "CALL", "resource": "system.info_"}]) as key:
        results = ssh(
            f"sudo -u {tuser["username"]} midclt -u ws://{ip}/api/current --api-key {key} call system.info",
            completes_response=True,
        )
        assert results["result"] is False, results


def test_denied_api_key_noauthz():
    with api_key([{"method": "CALL", "resource": "system.info"}]) as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key)
            # verify API key works as expected
            c.call("system.info")
            # system.version has no_authz_required
            # this should fail do to lack of authorization for
            # API key
            with pytest.raises(Exception):
                c.call("system.version")
            with pytest.raises(Exception):
                c.call("service.start", "cifs")
            with pytest.raises(Exception):
                c.call("service.update", "cifs", {"enable": True})
            auth_token = c.call("auth.generate_token")
        with client(auth=None) as c:
            assert c.call("auth.login_with_token", auth_token)
            # verify that token has same access rights
            c.call("system.info")
            with pytest.raises(Exception):
                c.call("system.version")
            with pytest.raises(Exception):
                c.call("service.start", "cifs")
            with pytest.raises(Exception):
                c.call("service.update", "cifs", {"enable": True})


def test_api_key_auth_session_list_terminate():
    with api_key([{"method": "CALL", "resource": "system.info"}]) as key:
        with client(auth=None) as c:
            assert c.call("auth.login_with_api_key", key)
            sessions = call("auth.sessions")
            my_sessions = []
            for s in sessions:
                if (
                    s["credentials"] == "API_KEY"
                    and s["credentials_data"]["api_key"]["name"] == "Test API Key"
                ):
                    my_sessions.append(s)
            assert len(my_sessions) == 1, sessions
            call("auth.terminate_session", my_sessions[0]["id"])
            with pytest.raises(Exception):
                c.call("system.info")
