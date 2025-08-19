import os
import pytest
import subprocess

from middlewared.utils import auditd

WITH_GPOS_STIG = True
# STIG test items
MODULE_STIG_RULE = "-a always,exit -F arch=b64 -S init_module,finit_module -F key=module-load"
SAMPLE_STIG_RULE = "-a always,exit -F arch=b64 -S all -F path=/etc/gshadow -F perm=wa -F key=identity"
IMMUTABLE_STIG_RULE = "-e 2"
# Non-STIG test items
SAMPLE_CE_RULES = ["-a always,exclude -F msgtype=USER_START", "-a always,exclude -F msgtype=SERVICE_START"]
# Common test items
REBOOT_RULE = "-a always,exit -F arch=b64 -S execve -F path=/usr/sbin/reboot -F key=escalation"

STIG_ASSERT_IN = [MODULE_STIG_RULE, SAMPLE_STIG_RULE, REBOOT_RULE]  # TODO:  IMMUTABLE_STIG_RULE when enabled
STIG_ASSERT_NOT_IN = SAMPLE_CE_RULES

NON_STIG_ASSERT_IN = [REBOOT_RULE] + SAMPLE_CE_RULES
NON_STIG_ASSERT_NOT_IN = [SAMPLE_STIG_RULE]


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

    for audit_rule in STIG_ASSERT_IN:
        assert audit_rule in stig_rule_set, f"stig_rule_set:\n{stig_rule_set}"
    for audit_rule in STIG_ASSERT_NOT_IN:
        assert audit_rule not in stig_rule_set, f"stig_rule_set:\n{stig_rule_set}"


def test__auditd_disable_gpos_stig(auditd_gpos_stig_disable):
    # With STIG disabled we should see NOSTIG_AUDIT_RULES
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.NOSTIG_AUDIT_RULES

    non_stig_rule_set = current_rule_set().splitlines()
    assert non_stig_rule_set != 'No rules'

    for audit_rule in NON_STIG_ASSERT_IN:
        assert audit_rule in non_stig_rule_set, f"non_stig_rule_set:\n{non_stig_rule_set}"
    for audit_rule in NON_STIG_ASSERT_NOT_IN:
        assert audit_rule not in non_stig_rule_set, f"non_stig_rule_set:\n{non_stig_rule_set}"
