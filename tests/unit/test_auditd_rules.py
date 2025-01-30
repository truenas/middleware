import os
import pytest
import subprocess

from middlewared.utils import auditd
from middlewared.utils import ProductType
from middlewared.plugins.system import product_type

CURRENT_PRODUCT_TYPE = product_type()
WITH_GPOS_STIG = True
print(f"MCG DEBUG: CURRENT_PRODUCT_TYPE = {CURRENT_PRODUCT_TYPE}")


def current_rule_set():
    rules = subprocess.run(['auditctl', '-l'], capture_output=True)
    return rules.stdout.decode().strip()


@pytest.fixture(
    params=[ProductType.ENTERPRISE, ProductType.COMMUNITY_EDITION],
    scope='function'
)
def auditd_gpos_stig_enable(request):
    auditd.set_audit_rules(WITH_GPOS_STIG, request.param)
    try:
        yield
    finally:
        auditd.set_audit_rules(not WITH_GPOS_STIG, CURRENT_PRODUCT_TYPE)


@pytest.fixture(
    params=[ProductType.ENTERPRISE, ProductType.COMMUNITY_EDITION],
    scope='function'
)
def auditd_gpos_stig_disable(request):
    try:
        auditd.set_audit_rules(not WITH_GPOS_STIG, request.param)
        yield
    finally:
        # make extra-sure we're disabled
        auditd.set_audit_rules(not WITH_GPOS_STIG, CURRENT_PRODUCT_TYPE)


@pytest.mark.parametrize('ruleset', auditd.AUDITRules)
def test__auditd_conf_rules_exist(ruleset):
    assert os.path.exists(os.path.join(auditd.CONF_AUDIT_RULES_DIR, ruleset))


def test__auditd_enable_gpos_stig(auditd_gpos_stig_enable):
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.STIG_AUDIT_RULES
    # rules = subprocess.run(['auditctl', '-l'], capture_output=True)
    # data = rules.stdout.decode().strip()
    # assert data != 'No rules'
    assert current_rule_set() != 'No rules'


def test__auditd_disable_gpos_stig(auditd_gpos_stig_disable):
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.NOSTIG_AUDIT_RULES

    # rules = subprocess.run(['auditctl', '-l'], capture_output=True)
    # data = rules.stdout.decode().strip()
    # assert data == 'No rules'
    assert current_rule_set() == 'No rules'
