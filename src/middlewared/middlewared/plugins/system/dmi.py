from truenas_pydmi.reader import read_dmi

from middlewared.service import Service, private


class SystemService(Service):
    @private
    def dmidecode_info(self):
        dmi = read_dmi()
        bb = dmi.baseboards[0] if dmi.baseboards else None
        return {
            'bios-release-date': (dmi.bios.release_date if dmi.bios else None) or "",
            'ecc-memory': dmi.ecc_memory,
            'baseboard-manufacturer': bb.manufacturer if bb else "",
            'baseboard-product-name': bb.product if bb else "",
            'system-manufacturer': dmi.system.manufacturer if dmi.system else "",
            'system-product-name': dmi.system.product_name if dmi.system else "",
            'system-serial-number': dmi.system.serial_number if dmi.system else "",
            'system-version': dmi.system.version if dmi.system else "",
            'has-ipmi': dmi.has_ipmi,
        }
