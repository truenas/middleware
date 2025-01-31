import os
import pytest
import subprocess

from middlewared.utils import auditd
from middlewared.utils import ProductType
from truenas_api_client import Client

pp = pytest.param
CURRENT_PRODUCT_TYPE = Client().call('system.product_type')
WITH_GPOS_STIG = True
SAMPLE_CE_RULE = "-a always,exclude -F msgtype=USER_START"


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
    params=[
        pp({"pt": ProductType.ENTERPRISE, "res": "No rules"}, id=ProductType.ENTERPRISE),
        pp({"pt": ProductType.COMMUNITY_EDITION, "res": SAMPLE_CE_RULE}, id=ProductType.COMMUNITY_EDITION)
    ],
    scope='function'
)
def auditd_gpos_stig_disable(request):
    prod_type = request.param["pt"]
    try:
        auditd.set_audit_rules(not WITH_GPOS_STIG, prod_type)
        yield request.param
    finally:
        # make extra-sure we're disabled
        auditd.set_audit_rules(not WITH_GPOS_STIG, CURRENT_PRODUCT_TYPE)


# Sanity check
def test__auditd_current_prod_type():
    assert CURRENT_PRODUCT_TYPE in dir(ProductType)


@pytest.mark.parametrize('ruleset', auditd.AUDITRules)
def test__auditd_conf_rules_exist(ruleset):
    assert os.path.exists(os.path.join(auditd.CONF_AUDIT_RULES_DIR, ruleset))


def test__auditd_enable_gpos_stig(auditd_gpos_stig_enable):
    # If STIG enabled then we should see no Community Edition Rules
    assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.STIG_AUDIT_RULES
    assert current_rule_set() != 'No rules'


def test__auditd_disable_gpos_stig(auditd_gpos_stig_disable):
    product_type = auditd_gpos_stig_disable["pt"]
    expected_result = auditd_gpos_stig_disable["res"]

    # If STIG disabled then we should see NOSTIG_AUDIT_RULES
    # and, if requested, Community Edition Rules.
    match product_type:
        case ProductType.ENTERPRISE:
            assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == auditd.NOSTIG_AUDIT_RULES
            assert current_rule_set() == 'No rules'
        case ProductType.COMMUNITY_EDITION:
            expected_list = [rule_file for rule_file in auditd.NOSTIG_AUDIT_RULES]
            expected_list += [rule_file for rule_file in set([auditd.AUDITRules.COMMUNITY])]
            assert set(os.listdir(auditd.AUDIT_RULES_DIR)) == set(expected_list)

    assert expected_result in current_rule_set().splitlines()
