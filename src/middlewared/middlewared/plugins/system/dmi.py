from functools import cache

from ixhardware import parse_dmi

from middlewared.service import private, Service


class SystemService(Service):
    @private
    @cache
    def dmidecode_info(self):
        dmi_info = self.dmidecode_info_internal()

        return {
            'bios-release-date': dmi_info.bios_release_date or "",
            'ecc-memory': dmi_info.ecc_memory,
            'baseboard-manufacturer': dmi_info.baseboard_manufacturer,
            'baseboard-product-name': dmi_info.baseboard_product_name,
            'system-manufacturer': dmi_info.system_manufacturer,
            'system-product-name': dmi_info.system_product_name,
            'system-serial-number': dmi_info.system_serial_number,
            'system-version': dmi_info.system_version,
            'has-ipmi': dmi_info.has_ipmi,
        }

    @private
    @cache
    def dmidecode_info_internal(self):
        return parse_dmi()
