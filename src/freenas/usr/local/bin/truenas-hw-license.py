#!/usr/bin/env python3
"""Write a bare hardware entitlement record on an iX appliance that holds no license.

Runs chrooted inside the new boot environment partway through an upgrade, before
middleware has ever started there. An appliance that shipped from iX carrying no
license blob reads as wholly unlicensed once the per-feature entitlement gates
apply, which withdraws capabilities the chassis was sold with. A minimal legacy
record restores them.

The record is stamped with a marker in its customer_key so the legacy parser can
tell it apart from a license an issuer actually signed, and bound it to the bare
hardware entitlement set instead of everything a legacy license implies. Nothing
is written if any license record already exists.
"""

import os
import sys
from datetime import date

from ixhardware import TRUENAS_UNKNOWN, get_chassis_hardware, parse_dmi
from licenselib.license import ContractHardware, ContractSoftware, ContractType, License

# Duplicated from middlewared/utils/license/constants.py and legacy.py rather than
# imported: middlewared.utils.license executes its package __init__, which pulls in
# truenas_pylicensed, the license daemon client and truenas_api_client -- far more
# than can be depended on inside a half-populated chroot midway through an upgrade.
LEGACY_LICENSE_FILE = "/data/license"
LICENSE_FILE = "/data/subsystems/truenas_license/license"
LICENSE_BACKUP = "/data/subsystems/truenas_license/license.bak"
HW_ONLY_MARKER = "TRUENAS-HW-ONLY-V1"

# An allowlist rather than a denylist, so a platform family added to ixhardware
# upstream is excluded here until someone decides it ships with this entitlement.
MINTABLE_PREFIXES = ("TRUENAS-R", "TRUENAS-Z")


def log(message):
    print(message, file=sys.stderr)


def main():
    for path in (LEGACY_LICENSE_FILE, LICENSE_FILE, LICENSE_BACKUP):
        if os.path.exists(path):
            log(f"{path} exists, leaving the license on this system alone")
            return

    dmi = parse_dmi()
    chassis = get_chassis_hardware(dmi)
    if chassis == TRUENAS_UNKNOWN:
        log("Chassis does not identify itself as iX hardware")
        return

    if "MINI" in chassis:
        log(f"{chassis} is a Mini")
        return

    if not chassis.startswith(MINTABLE_PREFIXES):
        log(f"{chassis} is not an eligible platform")
        return

    serial = dmi.system_serial_number.strip()
    if not serial:
        log("Chassis reports no system serial number")
        return

    if len(serial.encode()) > 16:
        log(f"System serial number does not fit the license field: {serial!r}")
        return

    model = chassis.removeprefix("TRUENAS-").split("-")[0]
    if len(model.encode()) > 16:
        log(f"Model does not fit the license field: {model!r}")
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

    fd = os.open(LEGACY_LICENSE_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        # The installer's pass over /data has already applied its modes by this point, so
        # nothing comes along afterwards to correct a file created here.
        os.fchmod(fd, 0o600)
        os.fchown(fd, 0, 0)
        os.write(fd, lic.dump() + b"\n")
    finally:
        os.close(fd)

    log(f"Wrote a hardware entitlement record for {chassis} ({serial})")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Failed to write a hardware entitlement record: {e!r}")

    # An upgrade must not fail over entitlement bookkeeping.
    sys.exit(0)
