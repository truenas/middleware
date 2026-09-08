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

import os
import sys
from datetime import date

from ixhardware import get_chassis_hardware, parse_dmi
from licenselib.license import ContractHardware, ContractSoftware, ContractType, License
from truenas_os_pyutils.io import atomic_write


LEGACY_LICENSE_FILE = "/data/license"
LICENSE_FILE = "/data/subsystems/truenas_license/license"
LICENSE_BACKUP = "/data/subsystems/truenas_license/license.bak"
HW_LICENSE_ERROR_FILE = "/data/truenas-hw-license.err"
HW_ONLY_MARKER = "TRUENAS-HW-ONLY-V1"

# An allowlist rather than a denylist, so a platform family added to ixhardware
# upstream is excluded here until someone decides it ships with this entitlement.
# Anything that reads as unknown or as a Mini fails it too.
MINTABLE_PREFIXES = ("TRUENAS-R",)


def record_error(message):
    """Leave a message middleware logs and deletes on first boot."""
    try:
        with atomic_write(HW_LICENSE_ERROR_FILE, "w", perms=0o600) as f:
            f.write(message + "\n")
    except Exception:
        pass


def main():
    for path in (LEGACY_LICENSE_FILE, LICENSE_FILE, LICENSE_BACKUP):
        if os.path.exists(path):
            return

    dmi = parse_dmi()
    chassis = get_chassis_hardware(dmi)
    if not chassis.startswith(MINTABLE_PREFIXES):
        return

    serial = dmi.system_serial_number.strip()
    if not serial:
        record_error(f"{chassis}: chassis reports no system serial number")
        return

    if len(serial.encode()) > 16:
        record_error(f"{chassis}: system serial number does not fit the license field: {serial!r}")
        return

    model = chassis.removeprefix("TRUENAS-").split("-")[0]
    if len(model.encode()) > 16:
        record_error(f"{chassis}: model does not fit the license field: {model!r}")
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
        record_error(f"{chassis}: failed to write {LEGACY_LICENSE_FILE} for serial {serial!r}: {e!r}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        record_error(f"unexpected failure: {e!r}")

    # An upgrade must not fail over entitlement bookkeeping.
    sys.exit(0)
