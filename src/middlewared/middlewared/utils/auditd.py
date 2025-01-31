import enum
import os
import stat
import subprocess

from middlewared.utils import ProductType

AUDIT_DIR = '/etc/audit'
AUDIT_RULES_DIR = os.path.join(AUDIT_DIR, 'rules.d')
AUDIT_PLUGINS_DIR = os.path.join(AUDIT_DIR, 'plugins.d')
CONF_AUDIT_RULES_DIR = '/conf/audit_rules'


class AUDITRules(enum.StrEnum):
    BASE = '10-base-config.rules'
    STIG = '30-stig.rules'
    PRIVILEGED = '31-privileged.rules'
    MODULE = '43-module-load.rules'
    FINALIZE = '99-finalize.rules'
    COMMUNITY = 'truenas-community-edition.rules'


STIG_AUDIT_RULES = frozenset([rules for rules in AUDITRules if rules != AUDITRules.COMMUNITY])
NOSTIG_AUDIT_RULES = frozenset([AUDITRules.BASE])


def set_audit_rules(gpos_stig_enabled: bool, truenas_product_type: str) -> None:
    """
    The rules:
        * STIG Rules CAN be applied to Community Edition Product
        * Community Edition Rules CAN NOT be applied with STIG enabled

    The rules will be enforced silently.
    """
    rules_set = STIG_AUDIT_RULES if gpos_stig_enabled else NOSTIG_AUDIT_RULES
    optional_rules_set = set()
    want_community_edition = bool(truenas_product_type == ProductType.COMMUNITY_EDITION)

    if want_community_edition and not gpos_stig_enabled:
        optional_rules_set = set([AUDITRules.COMMUNITY])

    # first remove all files that shouldn't be there
    for rules_file in os.listdir(AUDIT_RULES_DIR):
        full_path = os.path.join(AUDIT_RULES_DIR, rules_file)

        if rules_file not in [*rules_set, *optional_rules_set]:
            os.unlink(full_path)
        elif not stat.S_ISLNK(os.lstat(full_path).st_mode):
            os.unlink(full_path)
        elif os.readlink(full_path) != os.path.join(CONF_AUDIT_RULES_DIR, rules_file):
            os.unlink(full_path)

    for rules_file in [*rules_set, *optional_rules_set]:
        conf_path = os.path.join(CONF_AUDIT_RULES_DIR, rules_file)
        audit_path = os.path.join(AUDIT_RULES_DIR, rules_file)
        if os.path.exists(audit_path):
            continue

        os.symlink(conf_path, audit_path)

    subprocess.run(['augenrules', '--load'])
