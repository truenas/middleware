"""SMB stateful failover tests. HA only.

With stateful failover enabled, smbd sends its durable handles to truenas_smbhad, which
keeps a copy on the standby controller. After a failover, smbd restores the handles.

- Configuration tests: smb.conf, the daemon config and role on each controller, smbd
  running only on the active controller, no ctdb, and validation.
- Durable handle test: runs smbtorture truenas.durable.restore from the standby
  controller, crashes the active controller, and checks which handles come back.

At the end, the module fails back to the original active controller and restores the
SMB settings.
"""

import configparser
import contextlib
import os
import re
import shlex
import time
from types import SimpleNamespace
import uuid

import pytest

from auto_config import ha

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.failover import do_failover

pytestmark = pytest.mark.skipif(not ha, reason="SMB stateful failover tests require HA")

SMBHAD_BIN = "/usr/sbin/truenas_smbhad"
SMBHAD_CONF = "/etc/truenas_smbhad.conf"
# Oldest first
SMBD_LOGS = ("/var/log/samba4/log.smbd.old", "/var/log/samba4/log.smbd")
TORTURE_TEST = "truenas.durable.restore"

SHARE_NAME = "smb_ha_durable"
SMB_USER = "smbhauser"
SMB_PWD = "Abcd1234"
AUX_OPTION = "server string = SMB HA test"

HOLD_SECONDS = 900
WATCH_SECONDS = 1800
SETTLE_SECONDS = 5

CONFIG_TIMEOUT = 900
DURABLE_TIMEOUT = 3600
PROTECTION_TIMEOUT = 180
PREPARE_TIMEOUT = 180
VERIFY_TIMEOUT = 900
HA_RECOVERY_TIMEOUT = 900

UNPROTECTED_MARKERS = (
    "fenced: epoch",
    "standby lost:",
    "records to rehydrate",
    "no link key",
    "no link to a standby",
    "role ",
    "starting on boot",
    "stopped",
)


def wait_ha_ready(timeout=480, poll=5):
    deadline = time.monotonic() + timeout
    last = None
    while True:
        try:
            reasons = call("failover.disabled.reasons")
            connected = call("failover.remote_connected")
            peer = None
            if connected:
                peer = call("failover.call_remote", "failover.status")
            last = {"reasons": reasons, "connected": connected, "peer": peer}
            if not reasons and connected and peer == "BACKUP":
                return
        except Exception as exc:
            last = repr(exc)
        if time.monotonic() > deadline:
            raise TimeoutError(f"HA pair not ready after {timeout}s: {last}")
        time.sleep(poll)


def tail(text, lines=40):
    return "\n".join(text.splitlines()[-lines:])


def remote_sh(ip, script, **kwargs):
    return ssh(f"sh -c {shlex.quote(script)}", ip=ip, **kwargs)


def remote_cat(ip, path):
    with contextlib.suppress(Exception):
        return ssh(f"cat {shlex.quote(path)}", ip=ip, check=False)
    return ""


def start_detached(ip, script, log):
    remote_sh(ip, f"setsid nohup sh -c {shlex.quote(script)} > {shlex.quote(log)} 2>&1 < /dev/null &")


def wait_remote_file(ip, path, timeout, log=None, poll=5):
    """If `log` is given, stop early when smbtorture reports an error in it."""
    deadline = time.monotonic() + timeout
    reason = f"not written within {timeout}s"
    last = None
    while True:
        try:
            result = ssh(f"cat {shlex.quote(path)}", ip=ip, check=False, complete_response=True)
            if result["result"] and result["stdout"].strip():
                return result["stdout"]
            last = result["output"].strip()
            if log and re.search(r"^(failure|error): ", remote_cat(ip, log), re.MULTILINE):
                reason = "not written: smbtorture failed"
                break
        except Exception as exc:
            last = repr(exc)
        if time.monotonic() > deadline:
            break
        time.sleep(poll)
    output = f"\n{log}:\n{remote_cat(ip, log)}" if log else ""
    raise AssertionError(f"{path} on {ip} {reason} ({last}){output}")


def controller_time(ip):
    return int(ssh("date +%s", ip=ip).strip())


def smbhad_journal(ip, since=None):
    cmd = "journalctl -q -u truenas-smbhad -b -o cat --no-pager"
    if since is not None:
        cmd += f" --since @{since}"
    return ssh(cmd, ip=ip, check=False)


def smbhad_protected(journal):
    """Return True if, according to `journal`, the standby is in sync. The primary
    logs "protected: epoch N" when the standby has a full copy."""
    protected = False
    for line in journal.splitlines():
        if "protected: epoch" in line:
            protected = True
        elif any(marker in line for marker in UNPROTECTED_MARKERS):
            protected = False
    return protected


def wait_smbhad_protected(ip, since=None, timeout=PROTECTION_TIMEOUT, poll=2):
    deadline = time.monotonic() + timeout
    while True:
        journal = smbhad_journal(ip, since)
        if smbhad_protected(journal):
            return
        if time.monotonic() > deadline:
            raise AssertionError(
                f"truenas_smbhad on {ip} not protected by the standby within {timeout}s:\n{tail(journal)}"
            )
        time.sleep(poll)


def smbhad_role(ip):
    roles = re.findall(r"\brole (\w+)\s*$", smbhad_journal(ip), re.MULTILINE)
    return roles[-1] if roles else None


def torture_cmd(server_ip, phase, state, *options):
    return shlex.join(
        [
            "smbtorture",
            f"//{server_ip}/{SHARE_NAME}",
            "-U",
            f"{SMB_USER}%{SMB_PWD}",
            f"--option=torture:durable_phase={phase}",
            f"--option=torture:durable_state={state}",
            *options,
            TORTURE_TEST,
        ]
    )


@pytest.fixture(scope="module", autouse=True)
def ha_pair():
    """Skip if truenas_smbhad is not installed. Wait until the HA pair is ready, and
    fail back to the original active controller at the end."""
    if not ssh(f"test -x {SMBHAD_BIN}", check=False, complete_response=True)["result"]:
        pytest.skip(f"{SMBHAD_BIN} is not installed: this Samba does not replicate durable handles")

    wait_ha_ready()
    original = call("failover.node")
    yield
    with contextlib.suppress(Exception):
        wait_ha_ready()
    if call("failover.node") != original:
        do_failover(description="smb ha: restore original master")


@pytest.fixture(scope="module")
def stateful_failover_enabled():
    """Enable the SMB service and stateful failover, and restore both at the end.

    The SMB service must be enabled to start after a takeover. bindip is cleared so that
    smbd also listens on each controller's own IP, which the durable test uses."""
    smb_config = call("smb.config")
    cifs = call("service.query", [["service", "=", "cifs"]], {"get": True})
    if not cifs["enable"]:
        call("service.update", cifs["id"], {"enable": True})
    if cifs["state"] != "RUNNING":
        call("service.control", "START", "cifs", job=True)

    try:
        active = truenas_server.ha_ips()["active"]
        # The smbd restart resyncs the standby: only check messages from now on
        since = controller_time(active)
        call("smb.update", {"stateful_failover": True, "bindip": []})
        wait_smbhad_protected(active, since=since)
        yield
    finally:
        call("smb.update", {"stateful_failover": smb_config["stateful_failover"], "bindip": smb_config["bindip"]})
        if not cifs["enable"]:
            call("service.update", cifs["id"], {"enable": False})
        if cifs["state"] != "RUNNING":
            call("service.control", "STOP", "cifs", job=True)
        elif not call("service.started", "cifs"):
            call("service.control", "START", "cifs", job=True)


@pytest.fixture(scope="module")
def durable_share(stateful_failover_enabled):
    with dataset("smb_ha_durable", data={"share_type": "SMB"}) as ds:
        with user(
            {
                "username": SMB_USER,
                "full_name": SMB_USER,
                "group_create": True,
                "password": SMB_PWD,
                "smb": True,
            }
        ):
            with smb_share(os.path.join("/mnt", ds), SHARE_NAME, {"purpose": "DEFAULT_SHARE"}) as share:
                yield share


@pytest.fixture
def durable_client(durable_share):
    ips = truenas_server.ha_ips()
    workdir = f"/var/tmp/smb_ha_{uuid.uuid4().hex[:8]}"
    ssh(f"mkdir -p {workdir}", ip=ips["standby"])
    try:
        yield SimpleNamespace(active=ips["active"], standby=ips["standby"], workdir=workdir)
    finally:
        # The brackets keep pkill from matching its own command line
        pattern = shlex.quote(f"[{workdir[0]}]{workdir[1:]}")
        with contextlib.suppress(Exception):
            ssh(f"pkill -KILL -f {pattern}", ip=ips["standby"], check=False)
        with contextlib.suppress(Exception):
            ssh(f"rm -rf {workdir}", ip=ips["standby"], check=False)
        wait_ha_ready(timeout=HA_RECOVERY_TIMEOUT)


@pytest.mark.timeout(CONFIG_TIMEOUT)
def test_smb_conf_without_clustering(stateful_failover_enabled):
    """Stateful failover sets the samba option and does not enable clustering, which
    would disable it."""
    assert call("smb.getparm", "truenas stateful failover", "GLOBAL") is True
    assert call("smb.getparm", "clustering", "GLOBAL") is False


@pytest.mark.timeout(CONFIG_TIMEOUT)
@pytest.mark.parametrize("which", ["active", "standby"])
def test_smbhad_conf_names_node(stateful_failover_enabled, which):
    ip = truenas_server.ha_ips()[which]
    if which == "active":
        node = call("failover.node")
    else:
        node = call("failover.call_remote", "failover.node")
    content = ssh(f"cat {SMBHAD_CONF}", ip=ip)
    parser = configparser.ConfigParser()
    parser.read_string(content)
    assert parser.get("smbhad", "node", fallback=None) == node, content


@pytest.mark.timeout(CONFIG_TIMEOUT)
@pytest.mark.parametrize("which, role", [("active", "Primary"), ("standby", "Standby")])
def test_smbhad_runs_in_role(stateful_failover_enabled, which, role):
    if which == "active":
        running = call("service.started", "truenas_smbhad")
    else:
        running = call("failover.call_remote", "service.started", ["truenas_smbhad"])
    assert running

    ip = truenas_server.ha_ips()[which]
    assert smbhad_role(ip) == role, tail(smbhad_journal(ip))


@pytest.mark.timeout(CONFIG_TIMEOUT)
def test_standby_protects_active(stateful_failover_enabled):
    """The standby has a full copy of the durable handles of the active controller."""
    ips = truenas_server.ha_ips()
    wait_smbhad_protected(ips["active"])
    journal = smbhad_journal(ips["standby"])
    assert "replica complete:" in journal, tail(journal)


@pytest.mark.timeout(CONFIG_TIMEOUT)
def test_smbd_runs_on_active_only(stateful_failover_enabled):
    assert call("service.started", "cifs")
    assert not call("failover.call_remote", "service.started", ["cifs"])


@pytest.mark.timeout(CONFIG_TIMEOUT)
@pytest.mark.parametrize("which", ["active", "standby"])
def test_no_ctdb(stateful_failover_enabled, which):
    ip = truenas_server.ha_ips()[which]
    assert ssh("systemctl is-active ctdb", ip=ip, check=False).strip() != "active"
    assert not ssh("test -e /etc/ctdb/nodes", ip=ip, check=False, complete_response=True)["result"]


@pytest.mark.timeout(CONFIG_TIMEOUT)
def test_smb_options_rejected(stateful_failover_enabled):
    old = call("smb.config")["smb_options"]
    try:
        with pytest.raises(ValidationErrors) as ve:
            call("smb.update", {"smb_options": AUX_OPTION})
    finally:
        if call("smb.config")["smb_options"] != old:
            call("smb.update", {"smb_options": old})
    assert "smb_update.stateful_failover" in ve.value, str(ve.value)


@pytest.mark.timeout(CONFIG_TIMEOUT)
@pytest.mark.parametrize("purpose", ["LEGACY_SHARE", "MULTIPROTOCOL_SHARE"])
def test_incompatible_share_purpose_rejected(stateful_failover_enabled, purpose):
    name = f"smb_ha_{purpose.lower()}"
    with dataset(name, data={"share_type": "SMB"}) as ds:
        share = None
        try:
            with pytest.raises(ValidationErrors) as ve:
                share = call("sharing.smb.create", {"path": f"/mnt/{ds}", "name": name, "purpose": purpose})
        finally:
            if share is not None:
                call("sharing.smb.delete", share["id"])
    assert any("stateful SMB failover" in e.errmsg for e in ve.value.errors), str(ve.value)


@pytest.mark.timeout(DURABLE_TIMEOUT)
def test_durable_handles_survive_failover(durable_client):
    """Durable handles opened on the active controller can be reconnected after it
    crashes. truenas.durable.restore checks which handles must come back and which must
    not."""
    c = durable_client
    if TORTURE_TEST not in ssh(f"smbtorture --list {TORTURE_TEST}", ip=c.standby, check=False):
        pytest.skip(f"smbtorture on the controllers does not have {TORTURE_TEST}")

    assert not call("failover.call_remote", "service.started", ["cifs"])

    wait_smbhad_protected(c.active)
    state = f"{c.workdir}/state.txt"
    prepare = torture_cmd(truenas_server.ip, "prepare", state, f"--option=torture:durable_hold={HOLD_SECONDS}")
    start_detached(c.standby, f"cd {c.workdir} && exec {prepare}", f"{c.workdir}/prepare.out")
    wait_remote_file(c.standby, state, PREPARE_TIMEOUT, log=f"{c.workdir}/prepare.out")

    # smbd is active only after it restores the handles. Run verify right away:
    # handle G times out 20 s after the restore. Use the controller's own IP: the
    # VIP is firewalled until the takeover ends.
    verify = torture_cmd(c.standby, "verify", state)
    watcher = "\n".join(
        [
            f"cd {c.workdir} || exit 1",
            f"deadline=$(($(date +%s) + {WATCH_SECONDS}))",
            "until systemctl is-active --quiet smbd; do",
            '    if [ "$(date +%s)" -ge "$deadline" ]; then echo 124 > verify.rc; exit 1; fi',
            "    sleep 0.5",
            "done",
            f"{verify} > verify.out 2>&1 < /dev/null",
            "echo $? > verify.rc.tmp",
            "mv verify.rc.tmp verify.rc",
        ]
    )
    start_detached(c.standby, watcher, f"{c.workdir}/watcher.out")

    time.sleep(SETTLE_SECONDS)
    wait_smbhad_protected(c.active)
    standby_smbd = ssh("systemctl is-active smbd", ip=c.standby, check=False).strip()
    assert standby_smbd != "active", "smbd runs on the standby controller before the failover"

    # Crash instead of reboot: a clean shutdown disconnects the handles and starts
    # their timeouts early, so handle G would expire
    failover_started = controller_time(c.standby)
    do_failover(abusive=True, settle=False, description="smb ha: crash the active controller with durable handles")

    rc = wait_remote_file(c.standby, f"{c.workdir}/verify.rc", VERIFY_TIMEOUT).strip()
    restores = ssh(f"grep -h 'durable handles' {' '.join(SMBD_LOGS)}", ip=c.standby, check=False)
    journal = smbhad_journal(c.standby, since=failover_started)
    details = (
        f"verify output:\n{remote_cat(c.standby, f'{c.workdir}/verify.out')}\n"
        f"smbd restore messages on {c.standby}:\n{tail(restores, 10)}\n"
        f"truenas_smbhad on {c.standby} since the failover:\n{tail(journal)}"
    )
    assert rc == "0", f"{TORTURE_TEST} verify phase failed (exit code {rc})\n{details}"

    summaries = re.findall(r"durable handles after ([^:]+): (.*)", restores)
    assert summaries, f"smbd on {c.standby} logged no restore\n{details}"
    case, summary = summaries[-1]
    restored = re.match(r"restored (\d+),", summary)
    assert case == "failover" and restored and int(restored.group(1)) > 0, (
        f"smbd on {c.standby} did not restore handles after the failover: {case}: {summary}\n{details}"
    )

    rehydrated = re.findall(r"(\d+) records to rehydrate \(Replica\)", journal)
    assert rehydrated and int(rehydrated[-1]) > 0, (
        f"truenas_smbhad on {c.standby} did not load the copy from the old active controller\n{details}"
    )
