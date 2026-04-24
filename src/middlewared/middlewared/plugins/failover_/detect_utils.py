# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import logging
import pathlib
import subprocess
from functools import cache

from ixhardware import parse_dmi, PLATFORM_PREFIXES
from pyudev import Context

from middlewared.plugins.enclosure_.ses_enclosures2 import get_ses_enclosures
from middlewared.utils.version import parse_major_minor_version


logger = logging.getLogger(__name__)


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


@cache
def detect_platform() -> tuple[str, str]:
    HARDWARE = NODE = 'MANUAL'
    dmi = parse_dmi()
    product = dmi.system_product_name
    if not product:
        # no reason to continue since we've got no path forward
        return HARDWARE, NODE
    elif dmi.system_manufacturer == 'QEMU':
        serial = dmi.system_serial_number
        if not serial.startswith('ha') and not serial.endswith(('_c1', '_c2')):
            # truenas is often installed in KVM so we need to check our specific
            # strings in DMI and bail out early here
            return HARDWARE, NODE
        else:
            HARDWARE = 'IXKVM'
            NODE = 'A' if serial[-1] == '1' else 'B'
            return HARDWARE, NODE
    elif product == 'BHYVE':
        # bhyve host configures a scsi_generic device that when sent an inquiry will
        # respond with a string that we use to determine the position of the node
        ctx = Context()
        for i in ctx.list_devices(subsystem='scsi_generic'):
            if (model := i.attributes.get('device/model')) is not None:
                model = model.decode().strip() if isinstance(model, bytes) else model.strip()
                if model == 'TrueNAS_A':
                    NODE = 'A'
                    HARDWARE = 'BHYVE'
                    break
                elif model == 'TrueNAS_B':
                    NODE = 'B'
                    HARDWARE = 'BHYVE'
                    break

        return HARDWARE, NODE
    elif product.startswith('TRUENAS-F'):
        HARDWARE = 'LAJOLLA2'
        rv = subprocess.run(['ipmi-raw', '0', '3c', '0e'], stdout=subprocess.PIPE)
        if rv.stdout:
            # Viking info via VSS2249RQ Management Over IPMI document Section 5.5 page 15
            NODE = 'A' if rv.stdout.decode().strip()[-1] == '0' else 'B'

        return HARDWARE, NODE
    elif product.startswith('TRUENAS-H'):
        HARDWARE = 'SUBLIGHT'
        rv = subprocess.run(['ipmi-raw', '0', '6', '52', 'b', 'b2', '9', '0'], stdout=subprocess.PIPE)
        if rv.stdout:
            if (val := (int(rv.stdout.decode().strip()[-2:], base=16) & 1)) not in (0, 1):
                # h-series is a unique platform so best to have messages like these for ease of
                # troubleshooting if we're to hit something unexpected
                logger.error('Unexpected value returned from MCU: %d (expected 0 or 1)', val)
                return HARDWARE, NODE

            # (platform team has documentation if needed)
            # Bit 1 of 10th byte is 1 when "primary" controller from MCU 0xb2
            NODE = 'A' if val == 1 else 'B'

        return HARDWARE, NODE
    elif product.startswith('TRUENAS-V'):
        # HARDWARE depends on whether V1XX or V2XX
        match product[9]:
            case '1':
                HARDWARE = 'LUDICROUS'
            case '2':
                HARDWARE = 'PLAID'
            case _:
                return HARDWARE, NODE
        # 4IXGA backplane reports its SES product as NTB on the original
        # V-Series board and NTG on the new 4IXGA_PEX89032 (X710) board.
        # Both variants use the same -p/-s suffix to identify primary (A)
        # vs secondary (B) controller position.
        for s in get_ses_enclosures(False):
            if s.vendor == 'ECStream':
                if s.product in ('4IXGA-NTBp', '4IXGA-NTGp'):
                    NODE = 'A'
                    break
                elif s.product in ('4IXGA-NTBs', '4IXGA-NTGs'):
                    NODE = 'B'
                    break
        return HARDWARE, NODE
    elif not product.startswith(PLATFORM_PREFIXES):
        # users run TrueNAS on all kinds of exotic hardware. Most of the time, the
        # exotic hardware doesn't respond to standards conforming requests. Furthermore,
        # the enclosure feature is specific to our HA appliances so no reason to continue
        # down this path.
        return HARDWARE, NODE

    for enc in get_ses_enclosures(False):
        if enc.is_mseries:
            HARDWARE = 'ECHOWARP'
            if enc.product == '4024Sp':
                return HARDWARE, 'A'
            elif enc.product == '4024Ss':
                return HARDWARE, 'B'
        elif enc.is_xseries:
            HARDWARE = 'PUMA'
            esce = enc.elements.get('Enclosure Services Controller Electronics', {})
            for i in esce.values():
                if i['descriptor'].startswith(('ESCE A_', 'ESCE B_')):
                    node = i['descriptor'][5]
                    # We then cast the SES address (deduced from SES VPD pages)
                    # to an integer and subtract 1. Then cast it back to hexadecimal.
                    # We then compare if the SAS expander's SAS address is the same
                    # as the SAS expanders SES address.
                    ses_addr = hex(int(i['descriptor'][7:].strip(), 16) - 1)
                    sas_addr = pathlib.Path(
                        f'/sys/class/enclosure/{enc.pci}/device/sas_address'
                    ).read_text().strip()
                    if ses_addr == sas_addr:
                        return HARDWARE, node

    return HARDWARE, NODE
