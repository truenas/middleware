import io
import json
import time

import pytest
import requests

from middlewared.test.integration.assets.account import unprivileged_user as unprivileged_user_template
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.client import truenas_server, password
from middlewared.test.integration.utils.shell import assert_shell_works
from middlewared.service_exception import CallError


@pytest.fixture(scope="module")
def job_with_pipe():
    job_id, url = call("core.download", "config.save" , [], "debug.txz")
    try:
        yield job_id
    finally:
        call("core.job_abort", job_id)


@pytest.fixture(scope="module")
def download_token(job_with_pipe):
    return call("auth.generate_token", 300, {"filename": "debug.txz", "job": job_with_pipe}, True)


def test_download_auth_token_cannot_be_used_for_upload(download_token):
    r = requests.post(
        f"http://{truenas_server.ip}/_upload",
        headers={"Authorization": f"Token {download_token}"},
        data={
            "data": json.dumps({
                "method": "filesystem.put",
                "params": ["/tmp/upload"],
            })
        },
        files={
            "file": io.BytesIO(b"test"),
        },
        timeout=10
    )
    assert r.status_code == 403


def test_download_auth_token_cannot_be_used_for_websocket_auth(download_token):
    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", download_token)


@pytest.mark.timeout(30)
def test_token_created_by_token_can_use_shell():
    with client() as c:
        token = c.call("auth.generate_token", 300, {}, True)

        with client(auth=None) as c2:
            assert c2.call("auth.login_with_token", token)

            token2 = c2.call("auth.generate_token", 300, {}, True)
            assert_shell_works(token2, "root")


@pytest.fixture(scope="module")
def unprivileged_user():
    with unprivileged_user_template(
        username="test",
        group_name="test",
        privilege_name="test",
        roles=['READONLY_ADMIN'],
        web_shell=True,
    ):
        yield


def test_login_with_token_match_origin(unprivileged_user):
    token = ssh(
        "sudo -u test midclt -u ws://localhost/api/current -U test -P test1234 call auth.generate_token 300 '{}' true"
    ).strip()

    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", token)


def test_login_with_token_no_match_origin(unprivileged_user):
    token = ssh(
        "sudo -u test midclt -u ws://localhost/api/current -U test -P test1234 call auth.generate_token 300 '{}' false"
    ).strip()

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)


def test_token_is_for_one_time_use():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", token)


def test_kill_all_tokens_on_session_termination():
    token = call("auth.generate_token", 300)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)

        token = c.call("auth.generate_token")

        session = c.call("auth.sessions", [["current", "=", True]], {"get": True})
        call("auth.terminate_session", session["id"])

        with client(auth=None) as c:
            assert not c.call("auth.login_with_token", token)


def test_single_use_token():
    token = call("auth.generate_token", 300, {}, True, True)

    with client(auth=None) as c:
        assert c.call("auth.login_with_token", token)
        assert not c.call("auth.login_with_token", token)


def test_token_job_validation(job_with_pipe):
    with pytest.raises(CallError, match='job does not exist'):
        call("auth.generate_token", 300, {'job': -1})

    with unprivileged_user_client(roles=['READONLY_ADMIN']) as c:
        with pytest.raises(CallError, match='Job is not owned by current session'):
            c.call("auth.generate_token", 300, {'job': job_with_pipe})


def test_token_action_upload():
    """A plain (attribute-less) token authorizes a file upload via auth.get_token_for_action."""
    token = call('auth.generate_token', 300, {}, True, True)  # no attrs, match origin, single-use
    r = requests.post(
        f'http://{truenas_server.ip}/_upload',
        headers={'Authorization': f'Token {token}'},
        files={
            'data': (None, io.StringIO(json.dumps({
                'method': 'filesystem.put',
                'params': ['/tmp/token_action_upload'],
            }))),
            'file': (None, io.StringIO('token-action-payload')),
        },
        timeout=30,
    )
    r.raise_for_status()
    job_id = r.json()['job_id']
    assert call('core.job_wait', job_id, job=True) is True


def test_get_token_via_download():
    """A single-use download token is validated (and consumed) by auth.get_token via the download endpoint."""
    job_id, download_url = call('core.download', 'config.save', [], 'freenas.db')

    # First GET succeeds: auth.get_token validates the token and returns its attributes.
    r = requests.get(f'http://{truenas_server.ip}{download_url}', timeout=30)
    assert r.status_code == 200
    assert len(r.content) > 0

    # The token was single-use, so a second attempt is rejected.
    r = requests.get(f'http://{truenas_server.ip}{download_url}', timeout=30)
    assert r.status_code == 401


def test_generate_token_null_ttl():
    """Passing ttl=None falls back to the default token lifetime and still authenticates."""
    token = call('auth.generate_token', None)
    with client(auth=None) as c:
        assert c.call('auth.login_with_token', token)


def test_expired_token_is_rejected():
    """A token whose ttl has elapsed is purged on lookup and can no longer authenticate."""
    token = call('auth.generate_token', 1)
    time.sleep(3)
    with client(auth=None) as c:
        assert not c.call('auth.login_with_token', token)


@pytest.fixture(scope="module")
def reconnect_pref_user():
    # A dedicated user so the reconnect-token lifetime preference can be set without
    # touching root's (real) UI preferences; the user's attributes are removed on teardown.
    with unprivileged_user_template(
        username="reconpref",
        group_name="reconpref_grp",
        privilege_name="reconpref_priv",
        roles=["READONLY_ADMIN"],
        web_shell=False,
    ) as u:
        yield u


def _login_ex_with_reconnect(user):
    with client(auth=None) as c:
        return c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': user.username,
            'password': user.password,
            'login_options': {'reconnect_token': True},
        })


def test_reconnect_token_uses_ui_lifetime_preference(reconnect_pref_user):
    """The reconnect token ttl is derived from the UI 'preferences.lifetime' attribute."""
    with client(auth=(reconnect_pref_user.username, reconnect_pref_user.password)) as ac:
        ac.call('auth.set_attribute', 'preferences', {'lifetime': 120})

    resp = _login_ex_with_reconnect(reconnect_pref_user)
    assert resp['response_type'] == 'SUCCESS'
    assert isinstance(resp['reconnect_token'], str)


def test_reconnect_token_ignores_too_small_lifetime_preference(reconnect_pref_user):
    """A 'preferences.lifetime' below the minimum is ignored in favor of the default ttl."""
    with client(auth=(reconnect_pref_user.username, reconnect_pref_user.password)) as ac:
        ac.call('auth.set_attribute', 'preferences', {'lifetime': 5})

    resp = _login_ex_with_reconnect(reconnect_pref_user)
    assert resp['response_type'] == 'SUCCESS'
    assert isinstance(resp['reconnect_token'], str)


def test_reconnect_token_not_requested():
    """reconnect_token is null by default when not explicitly requested."""
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': 'root',
            'password': password(),
        })
        assert resp['response_type'] == 'SUCCESS'
        assert resp['reconnect_token'] is None


def test_reconnect_token_returned_on_request():
    """reconnect_token is a 64-character url-safe token when explicitly requested."""
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': 'root',
            'password': password(),
            'login_options': {'reconnect_token': True},
        })
        assert resp['response_type'] == 'SUCCESS'
        assert isinstance(resp['reconnect_token'], str)
        assert len(resp['reconnect_token']) == 64


def test_reconnect_token_can_reauthenticate():
    """A reconnect token returned from login_ex can be used to authenticate a new session."""
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': 'root',
            'password': password(),
            'login_options': {'reconnect_token': True},
        })
        assert resp['response_type'] == 'SUCCESS'
        token = resp['reconnect_token']

    with client(auth=None) as c:
        assert c.call('auth.login_with_token', token)


def test_reconnect_token_with_user_info_false():
    """reconnect_token is still returned when user_info=False (exercises the lazy auth.me fetch)."""
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': 'root',
            'password': password(),
            'login_options': {'user_info': False, 'reconnect_token': True},
        })
        assert resp['response_type'] == 'SUCCESS'
        assert resp['user_info'] is None
        assert len(resp['reconnect_token']) == 64


def test_reconnect_token_is_single_use():
    """Reconnect tokens are always single-use; a second login attempt with the same token fails."""
    with client(auth=None) as c:
        resp = c.call('auth.login_ex', {
            'mechanism': 'PASSWORD_PLAIN',
            'username': 'root',
            'password': password(),
            'login_options': {'reconnect_token': True},
        })
        assert resp['response_type'] == 'SUCCESS'
        token = resp['reconnect_token']

    with client(auth=None) as c:
        assert c.call('auth.login_with_token', token)

    with client(auth=None) as c:
        assert not c.call('auth.login_with_token', token)
