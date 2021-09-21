import subprocess

from middlewared.service import private, Service


class SystemService(Service):
    # DMI information is mostly static so cache it
    HAS_CACHE = False
    CACHE = {
        'ecc-memory': None,
        'baseboard-manufacturer': '',
        'baseboard-product-name': '',
        'system-manufacturer': '',
        'system-product-name': '',
        'system-serial-number': '',
        'system-version': '',
    }

    @private
    def dmidecode_info(self):
        if not SystemService.HAS_CACHE:
            cp = subprocess.run(['dmidecode', '-t', '1,2,16'], encoding='utf8', capture_output=True)
            self._parse_dmi(cp.stdout.splitlines())
            SystemService.HAS_CACHE = True

        return SystemService.CACHE

    @private
    def _parse_dmi(self, lines):
        for line in lines:
            if '# No SMBIOS nor DMI entry point found' in line:
                # means no DMI information available so fill out cache
                # with empty values so we don't continually try to fill it
                # (which defeats the entire purpose of having a cache)
                SystemService.CACHE = {i: '' for i in SystemService.CACHE}
                break

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
