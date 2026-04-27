"""Middleware → truenas-discoveryd plumbing integration tests.

Verifies that configuration mutations made through the middleware API
flow into the running ``truenas-discoveryd`` daemon's live state
(observed via the ``truenas-discovery-status`` CLI on the appliance).

Packet-level verification of mDNS announcements / NetBIOS name
registration / WSD probe-resolve is intentionally left to the
``truenas_pydiscovery`` repo's own CI; this file is scoped to the
middleware-owned plumbing (etc template → config file → systemd
reload → daemon picks up the change)."""
from __future__ import annotations

import contextlib
import json
import random
import string
import time

import pytest
from assets.websocket.service import ensure_service_started
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh

from protocols import smb_share


DIGITS = "".join(random.choices(string.digits, k=4))
DATASET_TM = f"tm{DIGITS}"
DATASET_SMB = f"smb{DIGITS}"

# Matches middlewared.utils.mdns.DevType.MACPRORACK — the literal
# that ends up in the ``model`` TXT record.  macOS Finder parses
# this form (``<model>@ECOLOR=r,g,b``) to pick the rack-mount icon.
DEV_INFO_MODEL = "MacPro7,1@ECOLOR=226,226,224"


# ---- helpers -------------------------------------------------------

def get_discovery_status() -> dict | None:
    """Return parsed JSON from ``truenas-discovery-status``.

    ``None`` means the CLI reported the daemon is not running (exits
    1 with "daemon not running" on stderr), which is a legitimate
    state when all three service-announcement toggles are off."""
    result = ssh("truenas-discovery-status", check=False, complete_response=True)
    if not result["result"]:
        return None
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return None


def discovery_is_active() -> bool:
    result = ssh(
        "systemctl is-active truenas-discoveryd",
        check=False, complete_response=True,
    )
    return result["result"] and "active" in (result["stdout"] or "")


def wait_for(predicate, timeout: float = 30.0, interval: float = 1.0):
    """Poll ``predicate()`` until it returns a truthy value or the
    timeout elapses.  Returns the final value (truthy or falsy)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        val = predicate()
        if val:
            return val
        time.sleep(interval)
    return predicate()


# Map service_announcement toggle keys to the daemon's child names.
_TOGGLE_TO_CHILD = {"mdns": "mdns", "netbios": "netbiosns", "wsd": "wsd"}


def _clear_stale_status_files(cfg: dict) -> None:
    """Remove per-child ``status.json`` files for protocols that will
    be disabled by *cfg*.

    ``truenas-discovery-status`` merges every per-protocol
    ``status.json`` it finds in ``/run/truenas-discovery/<child>/``,
    regardless of whether the current daemon instance actually hosts
    that child.  A file left behind by a previous daemon run (before a
    RESTART that drops the protocol) makes the CLI report a stale
    child that looks alive to the test.  Deleting the file here closes
    that window so the CLI output matches the running children."""
    for toggle, child in _TOGGLE_TO_CHILD.items():
        if not cfg.get(toggle):
            ssh(
                f"rm -f /run/truenas-discovery/{child}/status.json",
                check=False,
            )


def wait_for_enabled_set(cfg: dict, timeout: float = 30.0) -> None:
    """Block until the daemon's ``children`` dict matches *cfg*.

    *cfg* is a ``service_announcement`` mapping (mdns/netbios/wsd →
    bool).  Polls ``truenas-discovery-status`` until the reported
    children exactly match the enabled toggles, or the whole daemon
    is stopped when every toggle is off.

    The fixture/helper API calls that trigger a daemon RELOAD or
    RESTART return as soon as the middleware-side action is dispatched,
    not when the daemon has actually applied the change.  mDNS host
    rename reloads in particular re-probe every record (seconds of
    wall-clock work) and a SIGHUP arriving during that window is
    silently dropped by the daemon.  Blocking here until the daemon
    reflects the change prevents the *next* test's SIGHUP from racing
    an in-flight reload."""
    _clear_stale_status_files(cfg)
    expected = {
        child for toggle, child in _TOGGLE_TO_CHILD.items()
        if cfg.get(toggle)
    }
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = get_discovery_status()
        if not expected:
            # All off — daemon should be stopped.
            if status is None:
                return
        elif status is not None:
            if set(status.get("children", {}).keys()) == expected:
                return
        time.sleep(1)


@contextlib.contextmanager
def service_announcement(cfg: dict):
    """Scope a ``service_announcement`` override and restore on exit.

    Blocks until the daemon reflects *cfg* before yielding, and again
    after the restore, so the next API call doesn't race an in-flight
    reload."""
    prev = call("network.configuration.config")["service_announcement"]
    call("network.configuration.update", {"service_announcement": cfg})
    wait_for_enabled_set(cfg)
    try:
        yield
    finally:
        call("network.configuration.update", {"service_announcement": prev})
        wait_for_enabled_set(prev)


@contextlib.contextmanager
def ensure_aapl_extensions():
    """Enable AAPL extensions for the duration of the block."""
    cur = call("smb.config")["aapl_extensions"]
    if cur:
        yield
        return
    call("smb.update", {"aapl_extensions": True})
    try:
        yield
    finally:
        call("smb.update", {"aapl_extensions": False})


# ---- module-scoped fixtures ---------------------------------------

@pytest.fixture(autouse=True, scope="module")
def baseline_config():
    """Snapshot and restore the middleware-visible config that
    influences the discovery daemon.  Yields the captured original
    values so individual tests can reference them for cleanup."""
    network = call("network.configuration.config")
    smb = call("smb.config")
    orig = {
        "service_announcement": network["service_announcement"],
        "hostname": network["hostname"],
        "hostname_virtual": network.get("hostname_virtual", ""),
        "netbiosname": smb["netbiosname"],
        "netbiosalias": smb["netbiosalias"],
        "workgroup": smb["workgroup"],
        "description": smb["description"],
    }

    # Known-good starting state: all three announcements on.
    all_on = {"mdns": True, "netbios": True, "wsd": True}
    call("network.configuration.update", {"service_announcement": all_on})
    wait_for_enabled_set(all_on)
    try:
        yield orig
    finally:
        call("network.configuration.update", {
            "service_announcement": orig["service_announcement"],
            "hostname": orig["hostname"],
        })
        wait_for_enabled_set(orig["service_announcement"])
        call("smb.update", {
            "netbiosname": orig["netbiosname"],
            "netbiosalias": orig["netbiosalias"],
            "workgroup": orig["workgroup"],
            "description": orig["description"],
        })
        time.sleep(1)


# ---- sanity -------------------------------------------------------

class TestStatusSanity:
    """Smoke-test truenas-discovery-status itself."""

    def test_cli_returns_valid_json_with_pid_and_children(self):
        status = get_discovery_status()
        assert status is not None, "daemon should be running at baseline"
        assert isinstance(status.get("pid"), int)
        assert isinstance(status.get("children"), dict)

    def test_children_match_enabled_protocols(self):
        sa = call("network.configuration.config")["service_announcement"]
        status = get_discovery_status()
        assert status is not None
        enabled = {
            "mdns" if sa.get("mdns") else None,
            "netbiosns" if sa.get("netbios") else None,
            "wsd" if sa.get("wsd") else None,
        } - {None}
        assert set(status["children"].keys()) == enabled


# ---- announcement toggle ------------------------------------------

class TestAnnouncementToggle:
    """service_announcement flips flow into daemon child presence."""

    def test_mdns_toggle(self):
        with service_announcement({"mdns": False, "netbios": True, "wsd": True}):
            status = wait_for(
                lambda: (s := get_discovery_status())
                and "mdns" not in s["children"] and s,
            )
            final = get_discovery_status()
            diag = ssh(
                "echo '--- rundir ---'; "
                "ls -la /run/truenas-discovery/ /run/truenas-discovery/mdns/ 2>&1; "
                "echo '--- config ---'; "
                "cat /etc/truenas-discovery/truenas-discoveryd.conf 2>&1; "
                "echo '--- systemd ---'; "
                "systemctl show truenas-discoveryd "
                "-p MainPID -p ActiveState -p SubState -p ExecMainStartTimestamp 2>&1",
                check=False,
            )
            assert status, (
                f"daemon never saw mdns disabled\n"
                f"last status: {final}\n"
                f"diag:\n{diag}"
            )
            assert "mdns" not in status["children"]
        # Back on after scope exit.
        status = wait_for(
            lambda: (s := get_discovery_status()) and "mdns" in s["children"] and s,
        )
        assert status and "mdns" in status["children"]

    def test_netbios_toggle(self):
        with service_announcement({"mdns": True, "netbios": False, "wsd": True}):
            status = wait_for(
                lambda: (s := get_discovery_status())
                and "netbiosns" not in s["children"] and s,
            )
            final = get_discovery_status()
            assert status, (
                f"daemon never saw netbios disabled; last status: {final}"
            )
            assert "netbiosns" not in status["children"]

    def test_wsd_toggle(self):
        with service_announcement({"mdns": True, "netbios": True, "wsd": False}):
            status = wait_for(
                lambda: (s := get_discovery_status())
                and "wsd" not in s["children"] and s,
            )
            final = get_discovery_status()
            assert status, (
                f"daemon never saw wsd disabled; last status: {final}"
            )
            assert "wsd" not in status["children"]

    def test_all_disabled_stops_daemon(self):
        with service_announcement({"mdns": False, "netbios": False, "wsd": False}):
            stopped = wait_for(lambda: not discovery_is_active())
            assert stopped, "daemon stayed active with all announcements disabled"
            assert get_discovery_status() is None


# ---- hostname flow ------------------------------------------------

class TestHostnameFlow:
    """``network.configuration.update`` hostname flows into mdns/wsd."""

    def test_hostname_change_propagates(self, baseline_config):
        new_hostname = f"pydisc{DIGITS}"
        hostname_field = "hostname_virtual" if call("failover.licensed") else "hostname"
        call("network.configuration.update", {hostname_field: new_hostname})
        try:
            # mdns and wsd reload concurrently via the composite's
            # asyncio.gather; mdns may finish first (or vice versa).
            # Require BOTH to reflect the new hostname before yielding.
            status = wait_for(
                lambda: (s := get_discovery_status())
                and s.get("children", {}).get("mdns", {}).get("hostname", "").startswith(new_hostname)
                and s.get("children", {}).get("wsd", {}).get("hostname") == new_hostname
                and s,
                timeout=60,
            )
            final = get_discovery_status()
            assert status, (
                f"mdns/wsd hostname never reflected {new_hostname!r}; "
                f"last status: {final}"
            )
            assert status["children"]["mdns"]["hostname"].startswith(new_hostname)
            assert status["children"]["wsd"]["hostname"] == new_hostname
        finally:
            orig = baseline_config[hostname_field]
            call("network.configuration.update", {hostname_field: orig})
            # Block until the daemon's mDNS hostname reverts, so the
            # next test's SIGHUP doesn't race this restore's reload.
            wait_for(
                lambda: (s := get_discovery_status())
                and s.get("children", {}).get("mdns", {}).get("hostname", "").startswith(orig),
                timeout=60,
            )


# ---- SMB config flow ----------------------------------------------

class TestSmbConfigFlow:
    """smb.update fields flow into netbiosns automatically.

    Changing ``netbiosname``, ``netbiosalias`` or ``workgroup`` via
    ``smb.update`` triggers ``toggle_announcement`` internally — which
    regenerates ``truenas-discoveryd.conf`` and reloads the daemon —
    so tests here assert the change lands without an explicit reload.
    """

    def test_netbiosname_flows_into_netbiosns(self, baseline_config):
        new_name = f"PYDNB{DIGITS}"[:15]
        call("smb.update", {"netbiosname": new_name})
        try:
            status = wait_for(
                lambda: (s := get_discovery_status())
                and s.get("children", {}).get("netbiosns", {}).get("netbios_name") == new_name
                and s,
            )
            final = get_discovery_status()
            assert status, (
                f"netbiosns.netbios_name never became {new_name!r}; "
                f"last status: {final}"
            )
            assert status["children"]["netbiosns"]["netbios_name"] == new_name
        finally:
            orig = baseline_config["netbiosname"]
            call("smb.update", {"netbiosname": orig})
            wait_for(
                lambda: (s := get_discovery_status())
                and s.get("children", {}).get("netbiosns", {}).get("netbios_name") == orig,
            )

    def test_workgroup_flows_into_netbiosns_and_wsd(self, baseline_config):
        new_wg = f"PYDWG{DIGITS}"[:15]
        call("smb.update", {"workgroup": new_wg})
        try:
            status = wait_for(
                lambda: (s := get_discovery_status())
                and s.get("children", {}).get("netbiosns", {}).get("workgroup") == new_wg
                and s.get("children", {}).get("wsd", {}).get("workgroup") == new_wg
                and s,
            )
            final = get_discovery_status()
            assert status, (
                f"workgroup never became {new_wg!r} in netbiosns+wsd; "
                f"last status: {final}"
            )
            assert status["children"]["netbiosns"]["workgroup"] == new_wg
            assert status["children"]["wsd"]["workgroup"] == new_wg
        finally:
            orig = baseline_config["workgroup"]
            call("smb.update", {"workgroup": orig})
            wait_for(
                lambda: (s := get_discovery_status())
                and s.get("children", {}).get("netbiosns", {}).get("workgroup") == orig
                and s.get("children", {}).get("wsd", {}).get("workgroup") == orig,
            )


# ---- interfaces ---------------------------------------------------

class TestInterfacesFlow:
    """Interfaces middleware considers up appear in the daemon's
    per-protocol interface map."""

    def test_mdns_sees_configured_interfaces(self):
        status = get_discovery_status()
        assert status is not None
        mdns_ifaces = set(status["children"]["mdns"]["interfaces"].keys())

        # Middleware's view of "up" interfaces with IPv4 addresses —
        # those are what the etc template feeds into [discovery].interfaces.
        summary = call("network.general.summary")["ips"]
        expected = {
            name for name, info in summary.items()
            if "IPV4" in info and info["IPV4"]
        }

        assert mdns_ifaces, "mdns reported no interfaces"
        assert mdns_ifaces <= expected, (
            f"mdns interfaces {mdns_ifaces} exceed middleware-visible {expected}"
        )


# ---- SMB share services (uses TXT-enhanced status) ---------------

class TestSmbShareServices:
    """SMB share creates/deletes flow into mDNS services_registered.

    Time-Machine assertions target the per-instance TXT dict emitted
    by truenas_pydiscovery; if those tests ever fail with
    ``KeyError: 'txt'`` the deployed pydiscovery build predates the
    TXT enhancement (see truenas_pydiscovery#TBD)."""

    @staticmethod
    def _adisk_entries(status: dict) -> list[dict]:
        return [
            s for s in status["children"]["mdns"]["services_registered"]
            if "_adisk._tcp" in s["instance"]
        ]

    @staticmethod
    def _smb_entries(status: dict) -> list[dict]:
        return [
            s for s in status["children"]["mdns"]["services_registered"]
            if "_smb._tcp" in s["instance"] and not s["instance"].startswith("_")
        ]

    def test_basic_smb_share_appears_in_services(self):
        name = f"svc{DIGITS}"
        with ensure_service_started("cifs"), dataset(DATASET_SMB) as ds:
            with smb_share(f"/mnt/{ds}", {"name": name, "comment": "plumbing"}):
                status = wait_for(
                    lambda: (s := get_discovery_status())
                    and any(e["port"] == 445 for e in self._smb_entries(s or {}))
                    and s,
                    timeout=45,
                )
                assert status, "SMB service never appeared in mdns registrations"
                entries = self._smb_entries(status)
                assert entries
                assert all(e["port"] == 445 for e in entries), entries

    def test_smb_share_removal_removes_service(self):
        name = f"svcrm{DIGITS}"
        with ensure_service_started("cifs"), dataset(DATASET_SMB) as ds:
            with smb_share(f"/mnt/{ds}", {"name": name}):
                wait_for(
                    lambda: (s := get_discovery_status())
                    and self._smb_entries(s or {}),
                    timeout=45,
                )
            # Share ctx exited → deleted.  Give the daemon time to
            # tear the mDNS registration down.
            status = wait_for(
                lambda: (s := get_discovery_status())
                and not any(
                    name.lower() in e["instance"].lower()
                    for e in self._smb_entries(s or {})
                )
                and s,
                timeout=30,
            )
            assert status
            assert not any(
                name.lower() in e["instance"].lower()
                for e in self._smb_entries(status)
            )

    def test_time_machine_share_publishes_adisk_with_txt(self):
        name = f"tm{DIGITS}"
        with ensure_service_started("cifs"), ensure_aapl_extensions():
            with dataset(DATASET_TM) as ds:
                opts = {
                    "name": name,
                    "comment": "TM plumbing",
                    "purpose": "TIMEMACHINE_SHARE",
                }
                with smb_share(f"/mnt/{ds}", opts) as share_id:
                    status = wait_for(
                        lambda: (s := get_discovery_status())
                        and self._adisk_entries(s or {})
                        and s,
                        timeout=60,
                    )
                    assert status, "ADISK service never appeared"

                    adisk = self._adisk_entries(status)
                    assert len(adisk) >= 1

                    share = call("sharing.smb.query", [["id", "=", share_id]])[0]
                    vuid = share["options"]["vuid"]

                    # TXT values are CSV-packed "adVN=..,adVF=0x82,adVU=<vuid>"
                    # under dkN keys.  Find any dkN carrying the vuid
                    # and assert the sibling fields match the share.
                    found_vuid = False
                    for entry in adisk:
                        txt = entry.get("txt", {})
                        for key, value in txt.items():
                            if not key.startswith("dk"):
                                continue
                            parts = dict(
                                p.split("=", 1)
                                for p in value.split(",") if "=" in p
                            )
                            if parts.get("adVU") == vuid:
                                assert parts.get("adVN") == name, parts
                                assert parts.get("adVF") == "0x82", parts
                                found_vuid = True
                                break
                        if found_vuid:
                            break
                    assert found_vuid, (
                        f"vuid {vuid} not found in any ADISK TXT record; "
                        f"entries={adisk}"
                    )


# ---- always-on services ------------------------------------------

class TestAlwaysOnServices:
    """DEV_INFO and HTTP are rendered unconditionally on SINGLE /
    MASTER appliances (no service-started gating in the renderer),
    so both should appear in the mDNS services list at baseline."""

    @staticmethod
    def _entries_of(status: dict, service_type: str) -> list[dict]:
        return [
            s for s in status["children"]["mdns"]["services_registered"]
            if service_type in s["instance"]
        ]

    def test_device_info_advertised_with_model_txt(self):
        status = get_discovery_status()
        assert status is not None
        entries = self._entries_of(status, "_device-info._tcp")
        assert entries, "_device-info._tcp missing — DEV_INFO renderer gated?"
        # The renderer uses port 9 (discard) as a placeholder; the
        # record is discovery-only, not a real connect target.
        assert all(e["port"] == 9 for e in entries), entries
        for entry in entries:
            assert entry.get("txt", {}).get("model") == DEV_INFO_MODEL, entry

    def test_http_service_port_matches_ui_port(self):
        status = get_discovery_status()
        assert status is not None
        entries = self._entries_of(status, "_http._tcp")
        assert entries, "_http._tcp missing — HTTP renderer gated?"
        expected_port = int(call("system.general.config")["ui_port"])
        assert all(e["port"] == expected_port for e in entries), entries


# ---- gated-on services -------------------------------------------

class TestNutService:
    """``_nut._tcp`` is rendered only when the ``ups`` service is
    started-or-enabled.  Driving the positive case requires the
    dummy UPS driver scaffolding from ``test_530_ups.py`` (real
    hardware isn't available in CI); kept out of scope here.  The
    negative gating check below still catches regressions that
    would leak NUT into discovery when UPS is off."""

    def test_nut_absent_when_ups_stopped(self):
        svc = call(
            "service.query", [["service", "=", "ups"]], {"get": True},
        )
        if svc.get("state") == "RUNNING" or svc.get("enable"):
            pytest.skip("ups service is active; negative gating N/A")
        status = get_discovery_status()
        assert status is not None
        nut = [
            s for s in status["children"]["mdns"]["services_registered"]
            if "_nut._tcp" in s["instance"]
        ]
        assert not nut, (
            f"_nut._tcp advertised while ups is stopped: {nut}"
        )
