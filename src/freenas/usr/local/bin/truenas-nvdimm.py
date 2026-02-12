#!/usr/bin/env python3
import re
from subprocess import run
from packaging import version

from middlewared.utils.io import atomic_write

VERSION = re.compile(r'(?<=Version: ).*')
PRODUCT = re.compile(r'(?<=Product Name: ).*')
GEN3_MIN_VERS = version.Version('3.0').major
NVDIMM_CONF_FILE = '/etc/modprobe.d/truenas-nvdimm.conf'


def parse_dmi():
    output = run(['dmidecode', '-t1'], capture_output=True, encoding='utf8').stdout
    found_prod = PRODUCT.search(output)
    found_vers = VERSION.search(output)

    prod = vers = ''
    if found_prod:
        prod = found_prod.group(0)
    if found_vers:
        vers = found_vers.group(0)

    return prod, vers


def write_config(config):
    with atomic_write(NVDIMM_CONF_FILE, 'w', tmppath='/etc') as f:
        f.write('\n'.join(config) + '\n')


def is_m_series(prod):
    lower_prod = prod.lower()
    return all((
        lower_prod.startswith('truenas-m'),
        lower_prod.find('mini') == -1,
    ))


def main():
    try:
        prod, vers = parse_dmi()
    except Exception as e:
        print(f'Unhandled exception parsing DMI: {e}')
        return

    if not is_m_series(prod):
        # nvdimm config module is only relevant on m series.
        return

    try:
        parsed_version = version.parse(vers)
    except Exception as e:
        print(f'Unhandled exception ({e}) parsing DMI version ({vers!r})')
        return

    gen1_2 = gen3 = False
    if parsed_version.major == GEN3_MIN_VERS:
        # for now we only check to make sure that the current version is 3 because
        # we quickly found out that the SMBIOS defaults for the system-version value
        # from supermicro aren't very predictable. Since setting these values on a
        # system that doesn't support the dual-nvdimm configs leads to "no carrier"
        # on the ntb0 interface, we play it safe. The `gen3_min_vers` will need to be
        # changed as time goes on if we start tagging hardware with 4.0,5.0 etc etc
        gen3 = True
    else:
        # Means this is an m-series system that isn't tagged with "3.0" in the
        # version field of SMBIOS. This means the field is populated with OEM
        # default information. We've seen 0123456789 and 12345679 as some of the
        # default values so this is a catch-all since it's impossible to account
        # for all the possible values.
        gen1_2 = True

    options = [
        'options ntb driver_override="ntb_split"',
        'options ntb_transport use_dma=1',
    ]
    if gen1_2:
        # single nvdimm on gen1/2 hardware
        options.append('options ntb_split config="ntb_pmem:1:4:0,ntb_transport"')
    elif gen3:
        # dual nvdimm on gen3 hardware
        options.append('options ntb_hw_plx usplit=1')
        options.append('options ntb_split config="ntb_pmem:1:4:0,ntb_pmem:1:4:0,ntb_transport"')

    write_config(options)


if __name__ == '__main__':
    main()
