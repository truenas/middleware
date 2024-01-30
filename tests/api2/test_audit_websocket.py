# -*- coding=utf-8 -*-
from unittest.mock import ANY

import pytest

from middlewared.client import ClientException
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client, user
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.audit import expect_audit_log

pytestmark = pytest.mark.audit


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
            with pytest.raises(ClientException):
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
                        "credentials_data": {"username": ANY},
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
            with pytest.raises(ClientException):
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
                        "credentials_data": {"username": "root"},
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
                        "credentials_data": {"username": "root"},
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
                c.call("user.create", {"username": "sergey"})


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
                    "credentials_data": {"username": "root"},
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
                        "home": "/nonexistent",
                        "password": "********",
                        "home_create": True,
                    }
                ],
                "description": "Create user sergey",
            },
            "success": True,
        }
    ]):
        with user({
            "username": "sergey",
            "full_name": "Sergey",
            "group_create": True,
            "home": "/nonexistent",
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
                    "credentials_data": {"username": "root"},
                },
            },
            "event": "AUTHENTICATION",
            "event_data": {
                "credentials": {
                    "credentials": "LOGIN_PASSWORD",
                    "credentials_data": {"username": "root"},
                },
                "error": None,
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
                                "credentials_data": {"username": "root"},
                            },
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


def test_token_attributes_login_failed():
    token = call("auth.generate_token", 300, {"filename": "debug.txz", "job": 1020}, True)

    with client(auth=None) as c:
        with expect_audit_log([
            {
                "event": "AUTHENTICATION",
                "event_data": {
                    "credentials": {
                        "credentials": "TOKEN",
                        "credentials_data": {
                            "token": token,
                        },
                    },
                    "error": "Bad token",
                },
                "success": False,
            }
        ], include_logins=True):
            c.call("auth.login_with_token", token)


def test_api_key_login():
    with api_key([]) as key:
        with client(auth=None) as c:
            with expect_audit_log([
                {
                    "event": "AUTHENTICATION",
                    "event_data": {
                        "credentials": {
                            "credentials": "API_KEY",
                            "credentials_data": {
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
                        },
                    },
                    "error": "Invalid API key",
                },
                "success": False,
            }
        ], include_logins=True):
            c.call("auth.login_with_api_key", "invalid_api_key")


@pytest.mark.parametrize('logfile', ('/var/log/messages', '/var/log/syslog'))
def test_check_syslog_leak(logfile):
    entries = ssh(f'grep @cee {logfile}', check=False)
    assert '@cee' not in entries
