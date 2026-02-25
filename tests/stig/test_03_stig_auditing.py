"""
This module performs end-to-end testing of auditd rules from detection
detection by auditd to reporting by the TrueNAS audit subsystem.

The TrueNAS audit subsystem traps and reports the following keys:
    privileged, escalation, export, identity, time-change, module-load

See truenas_audit_handler.py
"""

import contextlib
import pytest

from auto_config import pool_name, password, user as runuser
from datetime import datetime, timedelta
from functions import async_SSH_done, async_SSH_start
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils import call, ssh
from os.path import dirname, join as path_join
from time import sleep

# Alias
pp = pytest.param

WITH_GPOS_STIG = True
WITHOUT_GPOS_STIG = False
STIG_USER = 'stiguser'
STIG_PWD = 'auditdtesting'
# As stored on TrueNAS
PRIVILEGED_RULE_FILE = '/conf/audit_rules/31-privileged.rules'
TRUENAS_STIG_RULE_FILE = '/conf/audit_rules/truenas-stig.rules'


def config_auditd(maybe_stig: bool, check=True):
    """
    This configures auditd rules and disables/enables io-uring as necessary
    """
    cmd = 'python3 -c "from middlewared.utils import auditd; from middlewared.utils.io import set_io_uring_enabled; '
    cmd += f'set_io_uring_enabled({not maybe_stig}); '
    cmd += f'auditd.set_audit_rules({maybe_stig});"'
    ssh(cmd, check=check)


def ausearch_ts():
    """Generate an ausearch compatible time stamp
       The timestamp is 3 seconds in the past"""
    ts = datetime.now() - timedelta(seconds=3)
    return ts.strftime("%m/%d/%y %H:%M:%S")


def assert_auditd_event(data: list, cmd: str, name=None, auid=None, euid=None):
    """
    Assert proctitle, auid and euid parts of the event (as necessary)
    The data and proctitle are required.  auid and euid are optional
    'name' field is supplied for 'identity' failure tests
    """
    found_proctitle = False
    proctitle_val = cmd.split()[0] if name is None else name

    for entry in data:
        if entry.startswith('---'):
            continue

        parts = entry.split()
        match (parts[0].split('='))[1]:
            case 'PROCTITLE':
                procpart = parts[4].split('=')
                assert procpart[0] == 'proctitle', f"msg parts={parts}"

                # Looking for proctitle entry for cmd
                proc_vals = f"{procpart[1]} " + ' '.join(parts[5:])
                if proctitle_val in proc_vals:
                    found_proctitle = True
                assert found_proctitle, f"Did not find {proctitle_val} in {proc_vals}, msg parts={parts}"

            case 'EXECVE':
                if found_proctitle:
                    assert cmd == (parts[5].split('='))[1], f"msg parts={parts}"  # exec_data

            case 'PATH':
                if found_proctitle and name is not None:
                    assert name == (parts[5].split('='))[1], f"msg parts={parts}"  # name

            case 'SYSCALL':
                if found_proctitle:
                    if name is None:
                        # split at 'a0' to avoid exit message
                        metaparts = (entry.split(' a0='))[1].split()
                        assert auid == (metaparts[7].split('='))[1], f"msg parts={parts}"  # syscall_auid
                    else:
                        assert 'success=no' == parts[6], f"msg parts={parts}"
                        assert 'EACCES(Permission' == (parts[7].split('='))[1], f"msg parts={parts}"

    # Confirm we found the auditd entry associated with the cmd
    assert found_proctitle, f"Did not find proctitle entry for {cmd}"


@contextlib.contextmanager
def stig_mode_audit(check=True):
    """Configure STIG mode level auditing without entering STIG mode"""

    rule_sanity_checks = [
        {'type': "path", 'path': "/usr/bin/mount", 'rulefile': f"{PRIVILEGED_RULE_FILE}"},
        {'type': "dir", 'path': "/etc", 'rulefile': f"{TRUENAS_STIG_RULE_FILE}"},
    ]

    rulefile_sanity_checks = [
        "/etc/audit/rules.d/31-privileged.rules",
        "/etc/audit/rules.d/truenas-stig.rules"
    ]

    IO_URING_ENABLED = 0

    try:
        config_auditd(WITH_GPOS_STIG, check=check)
        rules = ssh('auditctl -l')

        # Do some sanity checks
        io_uring_state = ssh("cat /proc/sys/kernel/io_uring_disabled")
        assert io_uring_state != IO_URING_ENABLED

        for rule in rule_sanity_checks:
            try:
                ssh(f"grep -q '{rule['type']}={rule['path']}' {rule['rulefile']}")
            except Exception:
                assert False, f"Failed to find {rule['type']}={rule['path']} in {rule['rulefile']}"

        for rulefile in rulefile_sanity_checks:
            try:
                ssh(f'test -e {rulefile}')
            except Exception:
                assert False, f"Failed to find {rulefile}"

        yield rules.splitlines()

    finally:
        config_auditd(WITHOUT_GPOS_STIG)
        io_uring_state = ssh("cat /proc/sys/kernel/io_uring_disabled")
        assert int(io_uring_state) == IO_URING_ENABLED


@pytest.fixture(scope='module')
def auditd_gpos_stig_enable():
    """Fixture to manage auditd configuration"""
    with stig_mode_audit() as rules:
        with user({
            'username': STIG_USER,
            'full_name': STIG_USER,
            'password': STIG_PWD,
            'home': f'/mnt/{pool_name}',
            'group_create': True,
            'shell': '/usr/bin/bash',
            'ssh_password_enabled': True,
            'groups': [40, 43],
        }):
            yield rules


@pytest.mark.parametrize('test_rule,param,key,sv', [
    pp("mount", ">/dev/null 2>&1", "privileged", "yes", id="mount - privileged"),
    pp("chmod 777", "/etc/nginx", "escalation", "yes", id="nginx conf - escalation"),
    pp("rm -f", "/var/log/nginx/error.log", "escalation", "no", id="nginx error.log - escalation"),
    pp("echo nefarious >>", "/etc/shadow", "identity", "no", id="/etc/shadow - identity"),
])
def test_audit_events(test_rule, param, key, sv, auditd_gpos_stig_enable):
    """
    The purpose of this test is to perform and end-to-end auditing validation
    on a sampling of rules.

    * Confirm selected rules get properly generated in auditd.
    * Confirm detection and proper reporting at the auditd and TrueNAS audit levels of
      selected rules.

    test_rule:  command
    param:  command parameter
    key: audit key
    sv: audit 'success' value
    """
    ruleset = auditd_gpos_stig_enable
    keycaps = key.upper()
    filter_op = "^"
    filter_key = test_rule

    # Confirm rules are configured for this key
    match key:
        case 'privileged':
            # 'privileged' events are about commands
            rule_path = path_join("/usr/bin", test_rule)

            # Confirm this command is privileged and in the active set of rules
            matching_rule = [r for r in ruleset if f"{rule_path} " in r and key in r]
            assert matching_rule != [], f"Missing {test_rule}"

        case 'escalation':
            # 'escalation' events are about an action on some object
            matching_rule = [r for r in ruleset if f"{param} " in r and key in r]
            assert matching_rule != [], f"Missing rule for {param}"

        case 'identity':
            # 'identity' events are about an action on some object
            # auditd cannot (yet) track across file replacements.
            # To work around this we track file actions by non-root users at the directory level.
            matching_rule = [r for r in ruleset if f"-F dir={dirname(param)} " in r and key in r]
            assert matching_rule != [], f"Missing rule for {param}"

            filter_op = "rin"
            filter_key = param

        case _:
            assert False, f"'{key}' key is not supported in this test."

    # Generate the event
    sleep(2)
    ssh(f"{test_rule} {param}", user=STIG_USER, password=STIG_PWD, check=False)
    sleep(1)

    # Confirm the auditd event
    ts = ausearch_ts()
    auditd_data = ssh(f"ausearch --input-logs -ts {ts} -sv {sv} -k {key} -i")

    name = param if key == 'identity' else None
    assert_auditd_event(auditd_data.splitlines(), test_rule, name, STIG_USER, STIG_USER)

    # Confirm TrueNAS audit subsystem records the event
    payload = {
        "services": ["SYSTEM"],
        "query-filters": [
            ["event", "=", keycaps],
            ["event_data.proctitle", filter_op, filter_key]],
        "query-options": {
            "select": ["event_data"],
            "order_by": ["-message_timestamp"], "limit": 1, "get": True}
    }
    event_data = call('audit.query', payload)['event_data']
    event_user = event_data['syscall']['AUID']
    assert event_user == STIG_USER, f"Expected {STIG_USER} but found {event_user!r}. " \
        f"event_data.syscall={event_data['syscall']}"


def test_missing_watched_directory():
    """Confirm truenas_audit_handler can handle a missing or renamed watched directory"""
    watched_dir = "/etc/proftpd/conf.d"

    try:
        # Setup the condition
        ssh(f"mv {watched_dir} {watched_dir}.MOVED")

        ah_log_tail = async_SSH_start("tail -n 0 -F /var/log/audit/audit_handler.log", runuser, password, truenas_server.ip)

        with stig_mode_audit(check=False):
            # Nothing to do here
            pass

        ah_log_data, errs = async_SSH_done(ah_log_tail, 5)    # 5 second timeout

        # We should detect no exceptions
        assert "PYTHON_EXCEPTION" not in ah_log_data

        # We log the missing directory detection
        assert "Watched directory is missing" in ah_log_data

    finally:
        ssh(f"mv {watched_dir}.MOVED {watched_dir}")
