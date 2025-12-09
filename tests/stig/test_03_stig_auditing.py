"""
This module performs end-to-end testing of auditd rules from detection
detection by auditd to reporting by the TrueNAS audit subsystem.

The TrueNAS audit subsystem traps and reports the following keys:
    privileged, escalation, export, identity, time-change, module-load

See truenas_audit_handler.py
"""

import pytest

from auto_config import pool_name
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, ssh
from os.path import join as path_join
from time import sleep

# Alias
pp = pytest.param

WITH_GPOS_STIG = True
WITHOUT_GPOS_STIG = False
STIG_USER = 'stiguser'
STIG_PWD = 'auditdtesting'
# As stored on TrueNAS
PRIVILEGED_RULE_FILE = '/conf/audit_rules/31-privileged.rules'
AUDIT_HANDLER_LOG = '/var/log/audit/audit_handler.log'


def config_auditd(maybe_stig: bool):
    """
    This configures auditd rules
    """
    cmd = 'python3 -c "from middlewared.utils import auditd;'
    cmd += f'auditd.set_audit_rules({maybe_stig})"'
    ssh(cmd)


def assert_auditd_event(data: list, cmd: str, auid=None, euid=None):
    """
    Assert proctitle, auid and euid parts of the event (as necessary)
    The data and proctitle are required.  auid and euid are optional
    """
    found_proctitle = False
    for entry in data:
        if entry.startswith('---'):
            continue

        parts = entry.split()
        match (parts[0].split('='))[1]:
            case 'PROCTITLE':
                procpart = parts[4].split('=')
                assert procpart[0] == 'proctitle'
                # Looking for proctitle entry for cmd
                if cmd.split()[0] in procpart[1]:
                    found_proctitle = True
            case 'EXECVE':
                if found_proctitle:
                    assert cmd == (parts[5].split('='))[1]  # exec_data
            case 'SYSCALL':
                if found_proctitle:
                    # split at 'a0' to avoid exit message
                    metaparts = (entry.split(' a0='))[1].split()
                    assert auid == (metaparts[7].split('='))[1]  # syscall_auid

    # Confirm we found the auditd entry associated with the cmd
    assert found_proctitle, f"Did not find proctitle entry for {cmd}"


@pytest.fixture(scope='module')
def auditd_gpos_stig_enable():
    """Fixture to manage auditd configuration"""
    config_auditd(WITH_GPOS_STIG)
    try:
        rules = ssh('auditctl -l')
        with user({
            'username': STIG_USER,
            'full_name': STIG_USER,
            'password': STIG_PWD,
            'home': f'/mnt/{pool_name}',
            'group_create': True,
            'shell': '/usr/bin/bash',
            'ssh_password_enabled': True,
        }):
            yield rules.splitlines()
    finally:
        config_auditd(WITHOUT_GPOS_STIG)
        # Cleanup auditd search info in /tmp
        ssh('rm -f /tmp/auditd_test')


@pytest.mark.parametrize('test_rule,param,key', [
    pp("mount", ">/dev/null 2>&1", "privileged", id="mount - privileged"),
    pp("chmod 777", "/etc/nginx", "escalation", id="nginx conf - escalation"),
    pp("rm -f", "/var/log/nginx/error.log", "escalation", id="nginx error.log - escalation"),
])
def test_privileged_and_escalation_events(test_rule, param, key, auditd_gpos_stig_enable):
    """
    The purpose of this test is to perform and end-to-end auditing validation
    on a sampling of rules.

    * Confirm selected privileged and escalation rules get properly generated in auditd.
    * Confirm detection and proper reporting at the auditd and TrueNAS audit levels of
      selected rules.
    """
    ruleset = auditd_gpos_stig_enable
    keycaps = key.upper()

    # Confirm rules are configured for this privileged or escalation rule
    match key:

        case 'privileged':
            # 'privileged' events are about commands
            rule_path = path_join("/usr/bin", test_rule)
            # Confirm the rule is 'priviledged and that the privileged rules are in rules.d
            ssh(f"grep -q 'path={rule_path}' {PRIVILEGED_RULE_FILE}")
            ssh('test -e /etc/audit/rules.d/31-privileged.rules')
            assert any(f"{rule_path} " in r for r in ruleset), f"Missing {test_rule}"

        case 'escalation':
            # 'escalation' events are about an action on some object
            assert any(f"{param} " in r for r in ruleset), f"Missing {param}:\n{ruleset}"

        case _:
            assert False, f"'{key}' key is not supported in this test."

    # First part: Confirm auditd records the event
    ssh(f"ausearch --input-logs --checkpoint /tmp/auditd_test --start now -k {key} -i", check=False)
    sleep(1)  # Must be at least 2 seconds between checkpoints
    ssh(f"{test_rule} {param}", user=STIG_USER, password=STIG_PWD, check=False)
    sleep(1)
    auditd_data = ssh(f"ausearch --input-logs --checkpoint /tmp/auditd_test --start checkpoint -k {key} -i ", check=False)
    assert_auditd_event(auditd_data.splitlines(), test_rule, STIG_USER, STIG_USER)

    # Second part: Confirm TrueNAS audit subsystem records the event and we can filter for it
    payload = {
        "services": ["SYSTEM"],
        "query-filters": [["event", "=", keycaps], ["event_data.proctitle", "^", test_rule]],
        "query-options": {"order_by": ["-message_timestamp"], "limit": 1, "get": True}
    }
    event = call('audit.query', payload)
    event_user = event['event_data']['syscall']['AUID']
    assert event_user == STIG_USER, f"Expected {STIG_USER} but found {event_user!r}"


def test_missing_watch_object_at_start():
    """
    Objects under a watch rule that are missing generate different auditd messages
    The process:
    1) Start in non-gpos mode
    2) Temporarily move a gpos audited directory
    3) Start gpos auditing
    4) Report any errors
    5) Restore temporary changes

    NOTE: While This condition is unhandled this test will generate an error report
          and the test will succeed.
          After the message is handled this test will fail and may be deleted.
    """
    watched_obj = "/etc/proftpd/conf.d"
    temp_append = ".renamed"
    # If everything is working, the size of /var/log/audit/audit_handler.log should be zero
    logsize = ssh(f'stat -c %s {AUDIT_HANDLER_LOG}').strip()
    log_contents = ssh(f"cat {AUDIT_HANDLER_LOG}")
    assert len(log_contents) <= 1, log_contents
    res = ""

    try:
        ssh(f"mv '{watched_obj}' '{watched_obj}{temp_append}'")
        config_auditd(True)
        sleep(1)
        res = ssh(f"cat {AUDIT_HANDLER_LOG}")
        assert "Unhandled auditd message" in res
    finally:
        # Restore
        ssh(f"mv '{watched_obj}{temp_append}' '{watched_obj}'")
        ssh(f"truncate -c --size 0 {AUDIT_HANDLER_LOG}")
        config_auditd(False)
