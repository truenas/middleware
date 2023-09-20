# -*- coding=utf-8 -*-
import contextlib
import re

import pytest

from middlewared.client import ClientException
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client, user
from middlewared.test.integration.assets.api_key import api_key
from middlewared.test.integration.utils import call, client, ssh


@contextlib.contextmanager
def expect_audit_log(text_or_texts, *, include_logins=False):
    if isinstance(text_or_texts, (list, tuple)):
        texts = text_or_texts
    else:
        texts = [text_or_texts]

    audit_log = ssh("cat /var/log/truenas_audit.log")

    yield

    new_audit_log = ssh("cat /var/log/truenas_audit.log")

    assert new_audit_log.startswith(audit_log)

    new_audit_log = new_audit_log[len(audit_log):].splitlines()

    if not include_logins:
        new_audit_log = [entry for entry in new_audit_log if not entry.endswith("Logged in")]

    assert len(new_audit_log) == len(texts)

    assert all(
        entry.endswith(text) if isinstance(text, str) else text.match(entry)
        for entry, text in zip(new_audit_log, texts)
    ), (new_audit_log, texts)


def test_unauthenticated_call():
    with client(auth=None) as c:
        with expect_audit_log("[NOT AUTHENTICATED] Create user sergey"):
            with pytest.raises(ClientException):
                c.call("user.create", {"username": "sergey", "full_name": "Sergey"})


def test_unauthorized_call():
    with unprivileged_user_client() as c:
        with expect_audit_log("[NOT AUTHORIZED] Create user sergey"):
            with pytest.raises(ClientException):
                c.call("user.create", {"username": "sergey", "full_name": "Sergey"})


def test_bogus_call():
    with client() as c:
        with expect_audit_log("[ERROR] Create user"):
            with pytest.raises(ValidationErrors):
                c.call("user.create", {})


def test_invalid_call():
    with client() as c:
        with expect_audit_log("[ERROR] Create user sergey"):
            with pytest.raises(ValidationErrors):
                c.call("user.create", {"username": "sergey"})


def test_valid_call():
    with expect_audit_log("[SUCCESS] Create user sergey"):
        with user({
            "username": "sergey",
            "full_name": "Sergey",
            "group_create": True,
            "home": "/nonexistent",
            "password": "password",
        }):
            pass


def test_password_login():
    with expect_audit_log("[SUCCESS] Logged in", include_logins=True):
        with client():
            pass


def test_password_login_failed():
    with expect_audit_log("[ERROR] Login failed (username='invalid')"):
        with client(auth=("invalid", ""), auth_required=False):
            pass


def test_token_login():
    token = call("auth.generate_token", 300, {}, True)

    with client(auth=None) as c:
        with expect_audit_log(re.compile(r".+\[\$token:root@.+\] \[SUCCESS\] Logged in"), include_logins=True):
            assert c.call("auth.login_with_token", token)


def test_token_login_failed():
    with client(auth=None) as c:
        with expect_audit_log("Login failed (invalid token)"):
            c.call("auth.login_with_token", "invalid")


def test_api_key_login():
    with api_key([]) as key:
        with client(auth=None) as c:
            with expect_audit_log(re.compile(r".+\[\$api_key:.+@.+\] \[SUCCESS\] Logged in"), include_logins=True):
                assert c.call("auth.login_with_api_key", key)


def test_api_key_login_failed():
    with client(auth=None) as c:
        with expect_audit_log("Login failed (invalid API key)"):
            c.call("auth.login_with_api_key", "invalid")
