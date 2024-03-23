# -*- coding=utf-8 -*-
import io
import json
import os
import pytest
import sys
from unittest.mock import ANY

import requests

from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.utils import call, url
from middlewared.test.integration.utils.audit import expect_audit_log

apifolder = os.getcwd()
sys.path.append(apifolder)
pytestmark = pytest.mark.audit
from functions import POST


def test_unauthenticated_call():
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
        r = requests.get(f"{url()}/api/v2.0/system/info", auth=("invalid", "password"))
        assert r.status_code == 401


def test_unauthenticated_upload_call():
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
        r = requests.post(
            f"{url()}/api/v2.0/resttest/test_input_pipe",
            auth=("invalid", "password"),
            files={
                "data": (None, io.StringIO('{"key": "value"}')),
                "file": (None, io.StringIO("FILE")),
            },
        )
        assert r.status_code == 401


def test_authenticated_call():
    user_id = None
    try:
        with expect_audit_log([
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "REST",
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
            },
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "REST",
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
                        }
                    ],
                    "description": "Create user sergey",
                },
                "success": True,
            },
        ], include_logins=True):
            r = POST("/user", {
                "username": "sergey",
                "full_name": "Sergey",
                "group_create": True,
                "home": "/nonexistent",
                "password": "password",
            })
            assert r.status_code == 200
            user_id = r.json()
    finally:
        if user_id is not None:
            call("user.delete", user_id)


def test_unauthorized_call():
    with unprivileged_user(
        username="unprivileged",
        group_name="unprivileged_users",
        privilege_name="Unprivileged users",
        allowlist=[],
        roles=[],
        web_shell=False,
    ) as u:
        with expect_audit_log([
            {
                "service_data": {
                    "vers": {
                        "major": 0,
                        "minor": 1,
                    },
                    "origin": ANY,
                    "protocol": "REST",
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
            r = requests.post(
                f"{url()}/api/v2.0/user",
                auth=(u.username, u.password),
                headers={"Content-type": "application/json"},
                data=json.dumps({"username": "sergey", "full_name": "Sergey"}),
            )
            assert r.status_code == 403, r.text


def test_bogus_call():
    with expect_audit_log([
        {
            "service_data": {
                "vers": {
                    "major": 0,
                    "minor": 1,
                },
                "origin": ANY,
                "protocol": "REST",
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
        response = POST("/user", {})
        assert response.status_code == 422
