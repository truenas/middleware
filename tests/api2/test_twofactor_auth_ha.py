import json
import shlex

import pytest

from middlewared.test.integration.assets.account import user as user_create
from middlewared.test.integration.assets.two_factor_auth import (
    enabled_twofactor_auth,
    get_2fa_totp_token,
    get_user_secret,
)
from middlewared.test.integration.utils import call, poll, ssh, truenas_server
from middlewared.test.integration.utils.failover import ha_enabled

pytestmark = pytest.mark.skipif(not ha_enabled, reason="HA only test")

TEST_USERNAME = "ha2fauser"
TEST_PASSWORD = "testpassword1234"
PROPAGATION_TIMEOUT = 60

# Drives a real PAM conversation against the API login stack of the node it runs on.
# `auth.login_ex` cannot be used on HA backup nodes.
PAM_PROBE = """\
import ipaddress
import json
import socket
import sys

from middlewared.utils.account.authenticator import UserPamAuthenticator
from middlewared.utils.origin import ConnectionOrigin
from truenas_pypam import PAMCode

username, password = sys.argv[1], sys.argv[2]
otp_token = None
if len(sys.argv) > 3:
    otp_token = sys.argv[3]

origin = ConnectionOrigin(
    family=socket.AF_INET,
    rem_addr=ipaddress.ip_address('169.254.20.30'),
    rem_port=8675,
    loc_addr=ipaddress.ip_address('169.254.20.40'),
    loc_port=8676,
)

hdl = UserPamAuthenticator(username=username, origin=origin)
resp = hdl.authenticate(username, password)
result = {'code': resp.code.name, 'reason': str(resp.reason)}
if otp_token and resp.code == PAMCode.PAM_CONV_AGAIN:
    oath_resp = hdl.authenticate_oath(otp_token)
    result['oath_code'] = oath_resp.code.name
    result['oath_reason'] = str(oath_resp.reason)

hdl.end()
print(json.dumps(result))
"""


def authenticate_on_standby(ip, otp_token=None):
    args = [TEST_USERNAME, TEST_PASSWORD]
    if otp_token:
        args.append(otp_token)

    argv = " ".join(shlex.quote(arg) for arg in args)
    return json.loads(
        ssh(f"python3 - {argv} <<'PROBE_EOF'\n{PAM_PROBE}PROBE_EOF", ip=ip)
    )


def test_standby_demands_second_factor():
    standby_ip = truenas_server.ha_ips()["standby"]

    with (
        enabled_twofactor_auth(),
        user_create(
            {
                "username": TEST_USERNAME,
                "full_name": TEST_USERNAME,
                "group_create": True,
                "password": TEST_PASSWORD,
            }
        ) as user_obj,
    ):
        call("user.renew_2fa_secret", TEST_USERNAME, {"interval": 30, "otp_digits": 6})
        resp = poll(
            lambda: authenticate_on_standby(standby_ip),
            condition=lambda result: result["code"] == "PAM_CONV_AGAIN",
            timeout=PROPAGATION_TIMEOUT,
            interval=2,
            message="standby controller authenticated the user without asking for a second factor",
        )
        assert "One-time password (OATH)" in resp["reason"], resp

        resp = authenticate_on_standby(
            standby_ip, get_2fa_totp_token(get_user_secret(user_obj["id"]))
        )
        assert resp["oath_code"] == "PAM_SUCCESS", resp

        call("user.unset_2fa_secret", TEST_USERNAME)
        poll(
            lambda: authenticate_on_standby(standby_ip),
            condition=lambda result: result["code"] == "PAM_SUCCESS",
            timeout=PROPAGATION_TIMEOUT,
            interval=2,
            message="standby controller still demanded a second factor after the secret was unset",
        )
