import re
from subprocess import run

DESIGNATION = re.compile(r'(?<=Designation: ).*')
BUS_ADDRESS = re.compile(r'(?<=Bus Address: ).*')
HEX_COLON = re.compile(r'^([0-9a-fA-F][0-9a-fA-F]:)+[0-9a-fA-F][0-9a-fA-F]$')


def wwn_as_colon_hex(hexstr):
    """
    Given a hex string '0xaabbccdd' (or 'naa.aabbccdd') return 'aa:bb:cc:dd'.
    """
    if isinstance(hexstr, str):
        if hexstr.startswith('0x'):
            # range(2,) to skip the leading 0x
            return ':'.join(hexstr[i:i + 2] for i in range(2, len(hexstr), 2))
        if hexstr.startswith('naa.'):
            # range(4,) to skip the leading naa.
            return ':'.join(hexstr[i:i + 2] for i in range(4, len(hexstr), 2))
        if HEX_COLON.match(hexstr):
            return hexstr


def colon_hex_as_naa(hexstr):
    """
    Given a colon hex string 'aa:bb:cc:dd'  return 'naa.aabbccdd'.
    """
    return 'naa.' + ''.join(hexstr.split(':'))


def str_to_naa(string):
    if string is None:
        return None
    if string.startswith('0x'):
        return 'naa.' + string[2:]
    if HEX_COLON.match(string):
        return 'naa.' + ''.join(string.split(':')).lower()
    if string.startswith('naa.'):
        return string


def wwpn_to_vport(wwpn, chan):
    if wwpn is None:
        return None
    # Similar to some code in isp_default_wwn (CORE os)
    seed = wwpn
    seed ^= 0x0100000000000000
    seed ^= ((chan + 1) & 0xf) << 56
    seed ^= (((chan + 1) >> 4) & 0xf) << 52
    return seed


def dmi_pci_slot_info():
    result = {}
    output = run(['dmidecode', '-t9'], capture_output=True, encoding='utf8').stdout
    for line in output.splitlines():
        if mat := DESIGNATION.search(line):
            designation = mat.group(0)
        if mat := BUS_ADDRESS.search(line):
            bus_addr = mat.group(0)
            result[bus_addr] = designation
    return result
