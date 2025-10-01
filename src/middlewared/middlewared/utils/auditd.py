import enum
import os
import stat
import subprocess

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
    TRUENAS_STIG = 'truenas-stig.rules'
    TRUENAS = 'truenas.rules'  # Rules for all versions of TrueNAS


# Set of rules applied for STIG mode
STIG_AUDIT_RULES = frozenset([
    AUDITRules.BASE, AUDITRules.STIG, AUDITRules.PRIVILEGED,
    AUDITRules.MODULE, AUDITRules.TRUENAS_STIG,
    AUDITRules.TRUENAS, AUDITRules.FINALIZE
])

# Set of rules applied in Non-STIG mode (default)
NOSTIG_AUDIT_RULES = frozenset([
    AUDITRules.BASE, AUDITRules.TRUENAS, AUDITRules.COMMUNITY
])


def set_audit_rules(gpos_stig_enabled: bool) -> None:
    """
    Apply STIG rule set or Non-STIG rule set
    """
    rules_set = STIG_AUDIT_RULES if gpos_stig_enabled else NOSTIG_AUDIT_RULES

    # first remove all files that shouldn't be there
    for rules_file in os.listdir(AUDIT_RULES_DIR):
        full_path = os.path.join(AUDIT_RULES_DIR, rules_file)

        if rules_file not in rules_set:
            os.unlink(full_path)
        elif not stat.S_ISLNK(os.lstat(full_path).st_mode):
            os.unlink(full_path)
        elif os.readlink(full_path) != os.path.join(CONF_AUDIT_RULES_DIR, rules_file):
            os.unlink(full_path)

    for rules_file in rules_set:
        conf_path = os.path.join(CONF_AUDIT_RULES_DIR, rules_file)
        audit_path = os.path.join(AUDIT_RULES_DIR, rules_file)
        if os.path.exists(audit_path):
            continue

        os.symlink(conf_path, audit_path)

    subprocess.run(['augenrules', '--load'])
