# -*- coding=utf-8 -*-
from unittest.mock import ANY

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client, user
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.assets.two_factor_auth import enabled_twofactor_auth, get_user_secret, get_2fa_totp_token
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.audit import expect_audit_log


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


@pytest.fixture(scope='function')
def sharing_admin_user(unprivileged_user_fixture):
    privilege = call('privilege.query', [['local_groups.0.group', '=', unprivileged_user_fixture.group_name]])
    assert len(privilege) > 0, 'Privilege not found'
    call('privilege.update', privilege[0]['id'], {'roles': ['SHARING_ADMIN']})

    try:
        yield unprivileged_user_fixture
    finally:
        call('privilege.update', privilege[0]['id'], {'roles': []})


def test_unauthenticated_call():
    with client(auth=None) as c:
        with expect_audit_log([
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "WEBSOCKET",
                    "credentials": None,
                },
                "event": "METHOD_CALL",
                "event_data": {
                    "authenticated": False,
                    "authorized": False,
                    "method": "user.create",
                    "params": [{"username": "sergey", "full_name": "Sergey"}],
                    "description": "Create user sergey",
                },
                "success": False,
            }
        ]):
            with pytest.raises(CallError):
                c.call("user.create", {"username": "sergey", "full_name": "Sergey"})


def test_unauthorized_call():
    with unprivileged_user_client() as c:
        with expect_audit_log([
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "WEBSOCKET",
                    "credentials": {
                        "credentials": "LOGIN_PASSWORD",
                        "credentials_data": {"username": ANY, "login_at": ANY, "login_id": ANY},
                    },
                },
                "event": "METHOD_CALL",
                "event_data": {
                    "authenticated": True,
                    "authorized": False,
                    "method": "user.create",
                    "params": [{"username": "sergey", "full_name": "Sergey"}],
                    "description": "Create user sergey",
                },
                "success": False,
            }
        ]):
            with pytest.raises(CallError):
                c.call("user.create", {"username": "sergey", "full_name": "Sergey"})


def test_bogus_call():
    with client() as c:
        with expect_audit_log([
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "WEBSOCKET",
                    "credentials": {
                        "credentials": "LOGIN_PASSWORD",
                        "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                    },
                },
                "event": "METHOD_CALL",
                "event_data": {
                    "authenticated": True,
                    "authorized": True,
                    "method": "user.create",
                    "params": [{}],
                    "description": "Create user",
                },
                "success": False,
            }
        ]):
            with pytest.raises(ValidationErrors):
                c.call("user.create", {})


def test_invalid_call():
    with client() as c:
        with expect_audit_log([
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "WEBSOCKET",
                    "credentials": {
                        "credentials": "LOGIN_PASSWORD",
                        "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                    },
                },
                "event": "METHOD_CALL",
                "event_data": {
                    "authenticated": True,
                    "authorized": True,
                    "method": "user.create",
                    "params": [{"username": "sergey", "password": "********"}],
                    "description": "Create user sergey",
                },
                "success": False,
            }
        ]):
            with pytest.raises(ValidationErrors):
                c.call("user.create", {"username": "sergey", "password": "password"})


def test_typo_in_secret_credential_name():
    with client() as c:
        with expect_audit_log([
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "WEBSOCKET",
                    "credentials": {
                        "credentials": "LOGIN_PASSWORD",
                        "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                    },
                },
                "event": "METHOD_CALL",
                "event_data": {
                    "authenticated": True,
                    "authorized": True,
                    "method": "user.create",
                    "params": [{"username": "sergey"}],
                    "description": "Create user sergey",
                },
                "success": False,
            }
        ]):
            with pytest.raises(ValidationErrors):
                c.call("user.create", {"username": "sergey", "passwrod": "password"})


def test_valid_call():
    with expect_audit_log([
        {
            "service_data": {
                "vers": {
                    "major": 0,
                    "minor": 1,
                },
                "origin": ANY,
                "protocol": "WEBSOCKET",
                "credentials": {
                    "credentials": "LOGIN_PASSWORD",
                    "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                },
            },
            "event": "METHOD_CALL",
            "event_data": {
                "authenticated": True,
                "authorized": True,
                "method": "user.create",
                "params": [
                    {
                        "username": "sergey",
                        "full_name": "Sergey",
                        "group_create": True,
                        "password": "********",
                        "home_create": True,
                    }
                ],
                "description": "Create user sergey",
            },
            "success": True,
        },
        {},
    ]):
        with user({
            "username": "sergey",
            "full_name": "Sergey",
            "group_create": True,
            "password": "password",
        }):
            pass


def test_password_login():
    with expect_audit_log([
        {
            "service_data": {
                "vers": {
                    "major": 0,
                    "minor": 1,
                },
                "origin": ANY,
                "protocol": "WEBSOCKET",
                "credentials": {
                    "credentials": "LOGIN_PASSWORD",
                    "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                },
            },
            "event": "AUTHENTICATION",
            "event_data": {
                "credentials": {
                    "credentials": "LOGIN_PASSWORD",
                    "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                },
                "error": None,
            },
            "success": True,
        },
        {
            "service_data": {
                "vers": {
                    "major": 0,
                    "minor": 1,
                },
                "origin": ANY,
                "protocol": "WEBSOCKET",
                "credentials": {
                    "credentials": "LOGIN_PASSWORD",
                    "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                },
            },
            "event": "LOGOUT",
            "event_data": {
                "credentials": {
                    "credentials": "LOGIN_PASSWORD",
                    "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                },
            },
            "success": True,
        }
    ], include_logins=True):
        with client():
            pass


def test_password_login_failed():
    with expect_audit_log([
        {
            "event": "AUTHENTICATION",
            "event_data": {
                "credentials": {
                    "credentials": "LOGIN_PASSWORD",
                    "credentials_data": {"username": "invalid"},
                },
                "error": "Bad username or password",
            },
            "success": False,
        }
    ], include_logins=True):
        with client(auth=("invalid", ""), auth_required=False):
            pass


def test_token_login():
    token = call("auth.generate_token", 300, {}, True)

    with client(auth=None) as c:
        with expect_audit_log([
            {
                "event": "AUTHENTICATION",
                "event_data": {
                    "credentials": {
                        "credentials": "TOKEN",
                        "credentials_data": {
                            "parent": {
                                "credentials": "LOGIN_PASSWORD",
                                "credentials_data": {"username": "root", "login_at": ANY, "login_id": ANY},
                            },
                            "token_id": ANY,
                            "username": "root",
                        },
                    },
                    "error": None,
                },
                "success": True,
            }
        ], include_logins=True):
            assert c.call("auth.login_with_token", token)


def test_token_login_failed():
    with client(auth=None) as c:
        with expect_audit_log([
            {
                "event": "AUTHENTICATION",
                "event_data": {
                    "credentials": {
                        "credentials": "TOKEN",
                        "credentials_data": {
                            "token": "invalid_token",
                        },
                    },
                    "error": "Invalid token",
                },
                "success": False,
            }
        ], include_logins=True):
            c.call("auth.login_with_token", "invalid_token")


def test_token_attributes_login_failed(download_token):
    with client(auth=None) as c:
        with expect_audit_log([
            {
                "event": "AUTHENTICATION",
                "event_data": {
                    "credentials": {
                        "credentials": "TOKEN",
                        "credentials_data": {
                            "token": download_token,
                        },
                    },
                    "error": "Bad token",
                },
                "success": False,
            }
        ], include_logins=True):
            c.call("auth.login_with_token", download_token)


def test_api_key_login():
    with api_key() as key:
        with client(auth=None) as c:
            with expect_audit_log([
                {
                    "event": "AUTHENTICATION",
                    "event_data": {
                        "credentials": {
                            "credentials": "API_KEY",
                            "credentials_data": {
                                "username": "root",
                                "login_at": ANY,
                                "login_id": ANY,
                                "api_key": {"id": ANY, "name": ANY},
                            },
                        },
                        "error": None,
                    },
                    "success": True,
                }
            ], include_logins=True):
                assert c.call("auth.login_with_api_key", key)


def test_api_key_login_failed():
    with client(auth=None) as c:
        with expect_audit_log([
            {
                "event": "AUTHENTICATION",
                "event_data": {
                    "credentials": {
                        "credentials": "API_KEY",
                        "credentials_data": {
                            "api_key": "invalid_api_key",
                            "username": None
                        },
                    },
                    "error": "Invalid API key",
                },
                "success": False,
            }
        ], include_logins=True):
            c.call("auth.login_with_api_key", "invalid_api_key")


def test_2fa_login(sharing_admin_user):
    user_obj_id = call('user.query', [['username', '=', sharing_admin_user.username]], {'get': True})['id']

    with enabled_twofactor_auth():
        call('user.renew_2fa_secret', sharing_admin_user.username, {'interval': 60})
        secret = get_user_secret(user_obj_id)

        with client(auth=None) as c:
            resp = c.call('auth.login_ex', {
                'mechanism': 'PASSWORD_PLAIN',
                'username': sharing_admin_user.username,
                'password': sharing_admin_user.password
            })
            assert resp['response_type'] == 'OTP_REQUIRED'
            assert resp['username'] == sharing_admin_user.username

            # simulate user fat-fingering the OTP token and then getting it correct on second attempt
            otp = get_2fa_totp_token(secret)

            with expect_audit_log([
                {
                    "event": "AUTHENTICATION",
                    "event_data": {
                        "credentials": {
                            "credentials": "LOGIN_TWOFACTOR",
                            "credentials_data": {
                                "username": sharing_admin_user.username,
                            },
                        },
                        "error": "One-time token validation failed.",
                    },
                    "success": False,
                }
            ], include_logins=True):
                resp = c.call('auth.login_ex', {
                    'mechanism': 'OTP_TOKEN',
                    'otp_token': 'canary'
                })
                assert resp['response_type'] == 'OTP_REQUIRED'
                assert resp['username'] == sharing_admin_user.username

            with expect_audit_log([
                {
                    "event": "AUTHENTICATION",
                    "event_data": {
                        "credentials": {
                            "credentials": "LOGIN_TWOFACTOR",
                            "credentials_data": {
                                "username": sharing_admin_user.username,
                                "login_at": ANY,
                                "login_id": ANY,
                            },
                        },
                        "error": None,
                    },
                    "success": True,
                }
            ], include_logins=True):
                resp = c.call('auth.login_ex', {
                    'mechanism': 'OTP_TOKEN',
                    'otp_token': otp
                })

                assert resp['response_type'] == 'SUCCESS'


@pytest.mark.parametrize('logfile', ('/var/log/messages', '/var/log/syslog'))
def test_check_syslog_leak(logfile):
    entries = ssh(f'grep @cee {logfile}', check=False)
    assert '@cee' not in entries
