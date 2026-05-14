import json

import pytest
import websocket

from middlewared.test.integration.assets.account import unprivileged_user as unprivileged_user_template
from middlewared.test.integration.utils import client, websocket_url
from middlewared.test.integration.utils.audit import expect_audit_log


def _attempt_shell_connect(token, options=None):
    payload = {"token": token}
    if options is not None:
        payload["options"] = options
    ws = websocket.create_connection(websocket_url() + "/websocket/shell")
    try:
        ws.send(json.dumps(payload))
        _, msg = ws.recv_data()
        return json.loads(msg.decode())
    finally:
        ws.close()


def _make_token(user):
    with client(auth=(user.username, user.password)) as c:
        return c.call("auth.generate_token", 300, {}, True)


@pytest.fixture(scope="module")
def shell_user_no_vm_role():
    with unprivileged_user_template(
        username="ws_no_vm",
        group_name="ws_no_vm_grp",
        privilege_name="Webshell no VM role",
        web_shell=True,
        roles=[],
    ) as t:
        yield t


@pytest.fixture(scope="module")
def shell_user_no_container_role():
    with unprivileged_user_template(
        username="ws_no_ct",
        group_name="ws_no_ct_grp",
        privilege_name="Webshell no container role",
        web_shell=True,
        roles=[],
    ) as t:
        yield t


@pytest.fixture(scope="module")
def shell_user_no_apps_role():
    with unprivileged_user_template(
        username="ws_no_app",
        group_name="ws_no_app_grp",
        privilege_name="Webshell no apps role",
        web_shell=True,
        roles=[],
    ) as t:
        yield t


def test_invalid_token_audited():
    with expect_audit_log([{
        "event": "WEBSHELL_AUTHENTICATION",
        "event_data": {
            "shell_type": "HOST",
            "target": None,
            "username": None,
            "error": "invalid token",
        },
        "success": False,
    }]):
        resp = _attempt_shell_connect("nonexistent-token-string")
        assert resp["msg"] == "failed"


def test_missing_vm_role_audited(shell_user_no_vm_role):
    token = _make_token(shell_user_no_vm_role)
    with expect_audit_log([{
        "event": "WEBSHELL_AUTHENTICATION",
        "event_data": {
            "shell_type": "VM",
            "target": {"vm_id": 1},
            "username": shell_user_no_vm_role.username,
            "error": "missing required role: VM_WRITE",
        },
        "success": False,
    }]):
        resp = _attempt_shell_connect(token, options={"vm_id": 1})
        assert resp["msg"] == "failed"


def test_missing_container_role_audited(shell_user_no_container_role):
    token = _make_token(shell_user_no_container_role)
    with expect_audit_log([{
        "event": "WEBSHELL_AUTHENTICATION",
        "event_data": {
            "shell_type": "CONTAINER",
            "target": {"container_id": 1},
            "username": shell_user_no_container_role.username,
            "error": "missing required role: CONTAINER_WRITE",
        },
        "success": False,
    }]):
        resp = _attempt_shell_connect(token, options={"container_id": 1})
        assert resp["msg"] == "failed"


def test_missing_apps_role_audited(shell_user_no_apps_role):
    token = _make_token(shell_user_no_apps_role)
    with expect_audit_log([{
        "event": "WEBSHELL_AUTHENTICATION",
        "event_data": {
            "shell_type": "APP",
            "target": {"app_name": "x", "container_id": "y"},
            "username": shell_user_no_apps_role.username,
            "error": "missing required role: APPS_WRITE",
        },
        "success": False,
    }]):
        resp = _attempt_shell_connect(token, options={"app_name": "x", "container_id": "y"})
        assert resp["msg"] == "failed"
