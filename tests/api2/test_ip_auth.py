import json

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import ssh


@pytest.mark.parametrize("url", ["127.0.0.1", "127.0.0.1:6000"])
@pytest.mark.parametrize("root", [True, False])
def test_tcp_connection_from_localhost(url, root):
    cmd = f"midclt -u ws://{url}/api/current call auth.sessions '[[\"current\", \"=\", true]]' '{{\"get\": true}}'"
    if root:
        assert json.loads(ssh(cmd))["credentials"] == "ROOT_TCP_SOCKET"
    else:
        with user({
            "username": "unprivileged",
            "full_name": "Unprivileged User",
            "group_create": True,
            "password": "test1234",
        }):
            result = ssh(f"sudo -u unprivileged {cmd}", check=False, complete_response=True)
            assert "Not authenticated" in result["stderr"]
