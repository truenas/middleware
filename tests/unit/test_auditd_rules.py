import os
import pytest
import subprocess

from middlewared.utils import auditd

WITH_GPOS_STIG = True
SAMPLE_STIG_RULE = "-a always,exit -F arch=b32 -F path=/etc/gshadow -F perm=wa -F key=identity"
SAMPLE_CE_RULE = "-a always,exclude -F msgtype=USER_START"


def current_rule_set():
    rules = subprocess.run(['auditctl', '-l'], capture_output=True)
    return rules.stdout.decode().strip()


@pytest.fixture(scope='function')
def auditd_gpos_stig_enable():
    auditd.set_audit_rules(WITH_GPOS_STIG)
    try:
        yield
    finally:
        auditd.set_audit_rules(not WITH_GPOS_STIG)


@pytest.fixture(scope='function')
def auditd_gpos_stig_disable():
    # make extra-sure we're disabled
    auditd.set_audit_rules(not WITH_GPOS_STIG)


@pytest.mark.parametrize('ruleset', auditd.AUDITRules)
def test__auditd_conf_rules_exist(ruleset):
    assert os.path.exists(os.path.join(auditd.CONF_AUDIT_RULES_DIR, ruleset))


def test__auditd_enable_gpos_stig(auditd_gpos_stig_enable):
    # With STIG enabled we should see no Community Edition Rules
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.STIG_AUDIT_RULES
    stig_rule_set = current_rule_set().splitlines()
    assert stig_rule_set != 'No rules'
    assert SAMPLE_STIG_RULE in stig_rule_set
    assert SAMPLE_CE_RULE not in stig_rule_set


def test__auditd_disable_gpos_stig(auditd_gpos_stig_disable):
    # With STIG disabled we should see NOSTIG_AUDIT_RULES
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.NOSTIG_AUDIT_RULES
    stig_rule_set = current_rule_set().splitlines()
    assert stig_rule_set != 'No rules'
    assert SAMPLE_STIG_RULE not in stig_rule_set
    assert SAMPLE_CE_RULE in stig_rule_set
