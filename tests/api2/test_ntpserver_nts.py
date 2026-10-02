import contextlib
import time

import pytest

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.system import reset_systemd_svcs
from truenas_api_client import ValidationErrors as ClientValidationErrors

CONFIG_FILE = "/etc/chrony/chrony.conf"
# The NTS servers the database migration 04a6293d595a adds to a stock configuration
DEFAULT_NTS_SERVERS = {"time.cloudflare.com", "ntppool1.time.nl"}
# The one test_nts_server_is_used actually talks to
LIVE_NTS_SERVER = "time.cloudflare.com"
STOCK_SERVERS = {f"{i}.debian.pool.ntp.org" for i in range(3)}
BAD_NTP = "172.16.0.0"


@contextlib.contextmanager
def ntp_servers_removed():
    """Run with no NTP servers, then restore the original ones.

    While an NTS server is configured, chronyd only adjusts the clock while one is reachable, so nothing a test adds
    may outlive it. The originals are restored with `force` so that the restore does not depend on reaching them.

    Every change restarts chronyd, and systemd refuses a sixth start within ten seconds, which leaves chronyd stopped.
    The count is cleared before the test and before the restore, so that chronyd runs for both.
    """
    original = call("system.ntpserver.query")
    for server in original:
        call("system.ntpserver.delete", server["id"])

    try:
        reset_systemd_svcs("chronyd")
        yield
    finally:
        for server in call("system.ntpserver.query"):
            call("system.ntpserver.delete", server["id"])

        reset_systemd_svcs("chronyd")
        for server in original:
            call("system.ntpserver.create", {k: v for k, v in server.items() if k != "id"} | {"force": True})


@contextlib.contextmanager
def nts_required():
    call("system.security.update", {"require_nts": True}, job=True)
    try:
        yield
    finally:
        call("system.security.update", {"require_nts": False}, job=True)


def config_lines(prefix):
    return [line for line in ssh(f"cat {CONFIG_FILE}").splitlines() if line.startswith(prefix)]


def server_lines():
    return config_lines("server ")


def test_stock_configuration_includes_nts_servers():
    """The database migration adds two, from different operators, to a system on the TrueNAS default servers."""
    servers = {server["address"]: server for server in call("system.ntpserver.query")}
    if set(servers) - DEFAULT_NTS_SERVERS != STOCK_SERVERS:
        pytest.skip("The NTP servers have been customized")
    ds = call("directoryservices.config")
    if ds["enable"] and ds["service_type"] in ("ACTIVEDIRECTORY", "IPA") and not DEFAULT_NTS_SERVERS & set(servers):
        pytest.skip("A domain member keeps its time sources, so the migration leaves the configuration alone")

    assert {address: servers[address]["nts"] for address in DEFAULT_NTS_SERVERS} == {
        address: True for address in DEFAULT_NTS_SERVERS
    }


def test_nts_is_rendered():
    with ntp_servers_removed():
        server = call("system.ntpserver.create", {"address": "127.0.0.1", "nts": True, "force": True})
        assert server["nts"] is True
        assert server_lines() == ["server 127.0.0.1 iburst maxpoll 10 minpoll 6 nts"]
        assert config_lines("authselectmode") == ["authselectmode prefer"]

        call("system.ntpserver.update", server["id"], {"nts": False, "force": True})
        assert server_lines() == ["server 127.0.0.1 iburst maxpoll 10 minpoll 6"]


def test_nts_key_establishment_is_checked():
    with ntp_servers_removed():
        with pytest.raises(ValidationErrors) as ve:
            call("system.ntpserver.create", {"address": "127.0.0.1", "nts": True})

        assert [error.attribute for error in ve.value.errors] == ["ntpserver_create.nts"]
        assert "unable to connect to TCP port 4460" in ve.value.errors[0].errmsg


def test_nts_caps_maxpoll():
    with ntp_servers_removed():
        with pytest.raises(ValidationErrors) as ve:
            call("system.ntpserver.create", {"address": "127.0.0.1", "nts": True, "force": True, "maxpoll": 22})

        assert [error.attribute for error in ve.value.errors] == ["ntpserver_create.maxpoll"]


@pytest.mark.parametrize("address", ["127.0.0.1\npidfile /root/ntp.pid", "127.0.0.1 nts", "127.0.0.1\t"])
def test_address_must_be_a_single_word(address):
    """It is interpolated bare into a `server` line of chrony.conf, which chronyd parses as root."""
    with ntp_servers_removed():
        with pytest.raises(ValidationErrors) as ve:
            call("system.ntpserver.create", {"address": address, "force": True})

        assert [error.attribute for error in ve.value.errors] == ["ntp_server_create.address"]


def test_alert_names_the_failing_nts_server():
    with ntp_servers_removed():
        call("system.ntpserver.create", {"address": BAD_NTP, "nts": True, "force": True})

        with mock("system.time_info", return_value={"uptime_seconds": 600}):
            reason = call("alert.run_source", "NTPHealthCheck")[0]["args"]["reason"]

        assert reason.startswith("No Active NTP peers")
        assert f"NTS key establishment is failing for: {BAD_NTP}." in reason


def test_nts_server_is_used():
    if not ssh(f"timeout 5 bash -c '</dev/tcp/{LIVE_NTS_SERVER}/4460'", check=False, complete_response=True)["result"]:
        pytest.skip(f"{LIVE_NTS_SERVER} is not reachable on TCP port 4460")

    with ntp_servers_removed():
        call("system.ntpserver.create", {"address": LIVE_NTS_SERVER, "nts": True})

        for _ in range(30):
            rows = [line.split(",") for line in ssh("chronyc -c -N authdata").splitlines()]
            # name, mode, key ID, type, key length, ...
            if any(row[:2] == [LIVE_NTS_SERVER, "NTS"] and int(row[4]) > 0 for row in rows):
                break

            time.sleep(1)
        else:
            assert False, rows


def test_require_nts_needs_an_nts_server():
    with ntp_servers_removed():
        call("system.ntpserver.create", {"address": "127.0.0.1", "force": True})

        # A job's validation errors reach the caller as the client's exception, not the middleware's
        with pytest.raises(ClientValidationErrors) as ve:
            call("system.security.update", {"require_nts": True}, job=True)

        assert [error.attribute for error in ve.value.errors] == ["system_security_update.require_nts"]
        assert call("system.security.config")["require_nts"] is False


def test_require_nts_keeps_an_nts_server_configured():
    with ntp_servers_removed():
        first = call("system.ntpserver.create", {"address": "127.0.0.1", "nts": True, "force": True})

        with nts_required():
            assert config_lines("authselectmode") == ["authselectmode require"]

            with pytest.raises(ValidationErrors) as ve:
                call("system.ntpserver.update", first["id"], {"nts": False, "force": True})
            assert [error.attribute for error in ve.value.errors] == ["ntpserver_update.nts"]

            with pytest.raises(CallError, match="The last NTS server cannot be deleted"):
                call("system.ntpserver.delete", first["id"])

            # chronyd would never use it
            with pytest.raises(ValidationErrors) as ve:
                call("system.ntpserver.create", {"address": "127.0.0.3", "force": True})
            assert [error.attribute for error in ve.value.errors] == ["ntpserver_create.nts"]

            # Not the last one any more
            call("system.ntpserver.create", {"address": "127.0.0.2", "nts": True, "force": True})
            call("system.ntpserver.delete", first["id"])

        assert config_lines("authselectmode") == ["authselectmode prefer"]
