import os
import pytest
import subprocess

from middlewared.utils import auditd


@pytest.fixture(scope='function')
def auditd_gpos_stig_enable():
    auditd.set_audit_rules(True)
    try:
        yield
    finally:
        auditd.set_audit_rules(False)


@pytest.fixture(scope='function')
def auditd_gpos_stig_disable():
    # make extra-sure we're disabled
    auditd.set_audit_rules(False)


@pytest.mark.parametrize('ruleset', auditd.AUDITRules)
def test__auditd_conf_rules_exist(ruleset):
    assert os.path.exists(os.path.join(auditd.CONF_AUDIT_RULES_DIR, ruleset))


def test__auditd_enable_gpos_stig(auditd_gpos_stig_enable):
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.STIG_AUDIT_RULES
    rules = subprocess.run(['auditctl', '-l'], capture_output=True)
    data = rules.stdout.decode().strip()
    assert data != 'No rules'


def test__auditd_disable_gpos_stig(auditd_gpos_stig_disable):
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.NOSTIG_AUDIT_RULES

    rules = subprocess.run(['auditctl', '-l'], capture_output=True)
    data = rules.stdout.decode().strip()
    assert data == 'No rules'
