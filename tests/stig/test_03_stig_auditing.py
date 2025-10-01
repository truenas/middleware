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
# from middlewared.utils import auditd
from time import sleep

# Alias
pp = pytest.param

WITH_GPOS_STIG = True
WITHOUT_GPOS_STIG = False
STIG_USER = 'stiguser'
STIG_PWD = 'auditdtesting'


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
                assert cmd.split()[0] in procpart[1]
                found_proctitle = True
            case 'EXECVE':
                if found_proctitle:
                    assert cmd == (parts[5].split('='))[1]  # exec_data
            case 'SYSCALL':
                if found_proctitle:
                    # split at 'a0' to avoid exit message
                    metaparts = (entry.split(' a0='))[1].split()
                    assert auid == (metaparts[7].split('='))[1]     # syscall_auid
                    assert euid == (metaparts[10].split('='))[1]    # syscall_euid


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
        # Cleanup /tmp
        ssh('rm /tmp/auditd_test')


# -a always,exit -F arch=b64 -F path=/usr/bin/ping -F perm=x -F auid>=900 -F auid!=unset -F key=privileged
@pytest.mark.parametrize('test_rule,param,key', [
    pp("ping", "-c1 127.0.0.1", "privileged", id="ping - privileged"),
    pp("chmod 777", "/etc/nginx", "escalation", id="nginx conf - escalation"),
    pp("rm -f", "/var/log/nginx/error.log", "escalation", id="nginx error.log - escalation"),
])
def test_privileged_and_escalation_events(test_rule, param, key, auditd_gpos_stig_enable):
    """Generate privileged and escalation events and confirm detection and reporting"""
    ruleset = auditd_gpos_stig_enable
    keycaps = key.upper()

    match key:
        case 'privilege':
            assert any(f"{test_rule} " in r for r in ruleset), f"Missing {test_rule}:\n{ruleset}"
        case 'escalation':
            assert any(f"{param} " in r for r in ruleset), f"Missing {param}:\n{ruleset}"

    # First part: Confirm auditd records the event
    # Must be at least 2 seconds between checkpoints
    ssh(f"ausearch --input-logs --checkpoint /tmp/auditd_test --start now -k {key} -i", check=False)
    sleep(1)
    ssh(f"{test_rule} {param}", user=STIG_USER, password=STIG_PWD, check=False)
    sleep(1)
    auditd_data = ssh(f"ausearch --input-logs --checkpoint /tmp/auditd_test --start checkpoint -k {key} -i ")
    assert_auditd_event(auditd_data.splitlines(), test_rule, STIG_USER, STIG_USER)

    # Second part: Confirm TrueNAS audit subsystem records the event and we can filter for it
    payload = {
        "services": ["SYSTEM"],
        "query-filters": [["event", "=", keycaps], ["event_data.proctitle", "^", test_rule]],
        "query-options": {"count": True}
    }
    count = call('audit.query', payload)
    assert count > 0, f"Did not find any {keycaps} events for {test_rule}"

    payload['query-options'] = {"offset": count - 1}
    event = call('audit.query', payload)
    assert len(event) == 1
    assert event[0]['event_data']['syscall']['AUID'] == STIG_USER, \
        f"Expected {STIG_USER}, but found {event['event_data']['syscall']['AUID']}"
