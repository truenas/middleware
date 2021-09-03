import subprocess

from middlewared.service import private, Service


class SystemService(Service):
    # DMI information is mostly static so cache it
    CACHE = {
        'ecc-memory': None,
        'baseboard-manufacturer': None,
        'baseboard-product-name': None,
        'system-manufacturer': None,
        'system-product-name': None,
        'system-serial-number': None,
        'system-version': None,
    }

    @private
    def dmidecode_info(self):
        if all(v is None for k, v in SystemService.CACHE.items()):
            cp = subprocess.run(['dmidecode', '-t', '1,2,16'], encoding='utf8', capture_output=True)
            self._parse_dmi(cp.stdout.splitlines())

        return SystemService.CACHE

    @private
    def _parse_dmi(self, lines):
        SystemService.CACHE = {i: '' for i in SystemService.CACHE}
        for line in lines:
            if 'DMI type 1,' in line:
                _type = 'SYSINFO'
            if 'DMI type 2,' in line:
                _type = 'BBINFO'

            if not line or ':' not in line:
                # "sections" are separated by the category name and then
                # a newline so ignore those lines
                continue

            sect, val = [i.strip() for i in line.split(':')]
            if sect == 'Manufacturer':
                SystemService.CACHE['system-manufacturer' if _type == 'SYSINFO' else 'baseboard-manufacturer'] = val
            elif sect == 'Product Name':
                SystemService.CACHE['system-product-name' if _type == 'SYSINFO' else 'baseboard-product-name'] = val
            elif sect == 'Serial Number' and _type == 'SYSINFO':
                SystemService.CACHE['system-serial-number'] = val
            elif sect == 'Version' and _type == 'SYSINFO':
                SystemService.CACHE['system-version'] = val
            elif sect == 'Error Correction Type':
                SystemService.CACHE['ecc-memory'] = 'ECC' in val
                # we break the for loop here since "16" is the last section
                # that gets processed and dmidecode always list the data in
                # the same order as requested (1,2,16) and "Error Correction Type"
                # doesn't appear in any of the other sections
                break
