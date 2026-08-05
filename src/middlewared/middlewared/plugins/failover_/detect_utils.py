# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from ixhardware import parse_dmi

from middlewared.utils.version import parse_major_minor_version


def is_vseries_v2_interconnect() -> bool:
    """True when this V-Series controller uses the new internal X710 LACP
    bond interconnect instead of the legacy external 10 GbE cable.

    Sourced from the DMI Type 1 "Version" field:
        < 2.0  (e.g. 1.0, 1.5, 1.99)  — external 10 GbE cable as internode0
        >= 2.0 (e.g. 2.0, 2.1, 3.0)   — internal LACP bond across the two
                                        on-board X710-AT2 ports as internode0
    Invalid / un-stamped DMI falls back to the >= 2.0 path and fires the
    vseries_unstamped_spd alert so support can see the bad SPD.

    Precondition: callers must have already verified this is V-Series
    hardware (HARDWARE in 'LUDICROUS' or 'PLAID'). The DMI Version field
    is not meaningful on other platforms, so this will return garbage on
    non-V-Series systems.
    """
    rev = parse_major_minor_version(parse_dmi().system_version)
    return rev is None or rev >= (2, 0)
