from subprocess import run

from middlewared.service import Service
from middlewared.schema import accepts, returns, Dict


class IpmiMcService(Service):

    class Config:
        namespace = 'ipmi.mc'
        cli_namespace = 'service.ipmi.mc'

    @accepts()
    @returns(Dict('mc_info', additional_attrs=True))
    def info(self, filters, options):
        """Return looks like:
            {
                'auxiliary_firmware_revision_information': '00000006h',
                'bridge': 'unsupported',
                'chassis_device': 'supported',
                'device_available': 'yes (normal operation)',
                'device_id': '32',
                'device_revision': '1',
                'device_sdrs': 'unsupported',
                'firmware_revision': '6.71',
                'fru_inventory_device': 'supported',
                'ipmb_event_generator': 'supported',
                'ipmb_event_receiver': 'supported',
                'ipmi_version': '2.0',
                'manufacturer_id': 'Super Micro Computer Inc. (10876)',
                'product_id': '2327',
                'sdr_repository_device': 'supported',
                'sel_device': 'supported',
                'sensor_device': 'supported'
            }
        """
        rv = {}
        if not self.middleware.call_sync('ipmi.is_loaded'):
            return rv

        out = run(['bmc-info', '--get-device-id'], capture_output=True)
        for line in filter(lambda x: x, out.stdout.decode().split('\n')):
            ele, status = line.split(':', 1)
            rv[ele.strip().replace(' ', '_').lower()] = status.strip()

        return rv
