#!/usr/bin/env python3
"""Write a bare hardware entitlement record on an iX appliance that holds no license.

Runs chrooted inside the new boot environment partway through an upgrade, before
middleware has ever started there. An appliance that shipped from iX carrying no
license blob resolves entitlements on the unlicensed column, which leaves nowhere
to gate a feature that every appliance of this class is meant to have. Writing a
minimal legacy record moves it onto the licensed column, where such a feature can
be granted without also granting it to commodity hardware.

The record is stamped with a marker in its customer_key so the legacy parser can
tell it apart from a license an issuer actually signed, and bound it to the bare
hardware entitlement set instead of everything a legacy license implies. Nothing
is written if any license record already exists.
"""

import json
import os
import sys
from datetime import date, datetime, timezone

from ixhardware import TRUENAS_UNKNOWN, get_chassis_hardware, parse_dmi
from licenselib.license import ContractHardware, ContractSoftware, ContractType, License
from truenas_os_pyutils.io import atomic_write

# Duplicated from middlewared/utils/license/constants.py and legacy.py rather than
# imported: middlewared.utils.license executes its package __init__, which pulls in
# truenas_pylicensed, the license daemon client and truenas_api_client -- far more
# than can be depended on inside a half-populated chroot midway through an upgrade.
LEGACY_LICENSE_FILE = "/data/license"
LICENSE_FILE = "/data/subsystems/truenas_license/license"
LICENSE_BACKUP = "/data/subsystems/truenas_license/license.bak"
HW_LICENSE_RESULT_FILE = "/data/truenas-hw-license.json"
HW_ONLY_MARKER = "TRUENAS-HW-ONLY-V1"

# An allowlist rather than a denylist, so a platform family added to ixhardware
# upstream is excluded here until someone decides it ships with this entitlement.
MINTABLE_PREFIXES = ("TRUENAS-R",)


def record_outcome(outcome, chassis=None, serial=None, model=None, error=None):
    """Leave a record middleware relays into middlewared.log and deletes on first boot.

    Every outcome is recorded, not just failures: a chassis reading as unknown is
    indistinguishable here from dmidecode having failed,
    so which outcomes deserve attention is middleware's call, not ours.
    """
    try:
        record = {
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "outcome": outcome,
            "chassis": chassis,
            "serial": serial,
            "model": model,
            "error": None if error is None else str(error)[:512],
        }
        with atomic_write(HW_LICENSE_RESULT_FILE, "w", perms=0o600) as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def main():
    for path in (LEGACY_LICENSE_FILE, LICENSE_FILE, LICENSE_BACKUP):
        if os.path.exists(path):
            record_outcome("license_present")
            return

    dmi = parse_dmi()
    chassis = get_chassis_hardware(dmi)
    if chassis == TRUENAS_UNKNOWN:
        record_outcome("chassis_unknown")
        return

    if "MINI" in chassis:
        record_outcome("mini", chassis=chassis)
        return

    if not chassis.startswith(MINTABLE_PREFIXES):
        record_outcome("ineligible_platform", chassis=chassis)
        return

    serial = dmi.system_serial_number.strip()
    if not serial:
        record_outcome("serial", chassis=chassis, error="Chassis reports no system serial number")
        return

    if len(serial.encode()) > 16:
        record_outcome(
            "serial",
            chassis=chassis,
            serial=serial,
            error=f"System serial number does not fit the license field: {serial!r}",
        )
        return

    model = chassis.removeprefix("TRUENAS-").split("-")[0]
    if len(model.encode()) > 16:
        record_outcome(
            "model",
            chassis=chassis,
            serial=serial,
            model=model,
            error=f"Model does not fit the license field: {model!r}",
        )
        return

    lic = License(
        1,
        # Derived exactly the way the license-status alert derives the running system's
        # model, so that alert cannot report a mismatch against the record written here.
        model,
        serial,
        # An empty HA serial holds the parsed type at ENTERPRISE_SINGLE, keeping
        # failover.licensed false; a populated one would advertise a single head as a pair.
        "",
        ContractType.legacy,
        ContractHardware.parts,
        ContractSoftware.none,
        date.today(),
        36500,
        "",
        HW_ONLY_MARKER,
        [],
        [],
    )

    try:
        with atomic_write(LEGACY_LICENSE_FILE, "wb", perms=0o600, noclobber=True) as f:
            f.write(lic.dump() + b"\n")
    except Exception as e:
        record_outcome("write", chassis=chassis, serial=serial, model=model, error=repr(e))
        return

    record_outcome("written", chassis=chassis, serial=serial, model=model)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        record_outcome("unexpected", error=repr(e))

    # An upgrade must not fail over entitlement bookkeeping.
    sys.exit(0)
