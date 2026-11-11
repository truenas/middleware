#!/usr/bin/env python3
"""Keep scst disabled at boot in a new boot environment where it must not start at boot.

Runs chrooted inside the new boot environment partway through an upgrade, after the installer
has enabled the units listed in the old /data/user-services.json. Older middleware recorded scst
there as enabled even on HA (where middleware starts it from vrrp_master / vrrp_backup) and in
LIO mode, so the first boot of the new environment would start it before middleware could
disable it.

Neither middleware nor the license daemon runs here, so the license cannot be consulted. HA is
instead judged from the stored ALUA flag together with the hardware platform: ALUA is the case
where an early start breaks the standby, and the platform check keeps a stray ALUA flag on a
single node from disabling scst there.
"""

import subprocess
import sys

from middlewared.utils.db import query_config_table
from middlewared.utils.hardware import detect_platform
from middlewared.utils.iscsi.constants import ISCSIMODE


def scst_blocked_at_boot():
    # The database has already been migrated, so iscsi_mode exists.
    config = query_config_table("services_iscsitargetglobalconfiguration", prefix="iscsi_")
    if config["mode"] == ISCSIMODE.LIO:
        return True
    return bool(config["alua"]) and detect_platform()[0] != "MANUAL"


def main():
    # If the check raises, the script exits non-zero and leaves scst unchanged.
    if scst_blocked_at_boot():
        return subprocess.run(["systemctl", "disable", "scst"], check=False).returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
