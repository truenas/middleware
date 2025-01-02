from ixhardware.chassis import TRUENAS_UNKNOWN

from middlewared.service import private, Service


class VirtLicenseGlobalService(Service):

    class Config:
        namespace = 'virt.global'

    @private
    async def license_active(self, instance_type=None):
        """
        If this is iX enterprise hardware and has NOT been licensed to run virt plugin
        then this will return False, otherwise this will return true.
        """
        system_chassis = await self.middleware.call('truenas.get_chassis_hardware')
        if system_chassis == TRUENAS_UNKNOWN or 'MINI' in system_chassis:
            # 1. if it's not iX branded hardware
            # 2. OR if it's a MINI, then allow containers/vms
            return True

        license_ = await self.middleware.call('system.license')
        if license_ is None:
            # it's iX branded hardware but has no license
            return False

        if instance_type is None:
            # licensed JAILS (containers) and/or VMs
            return any(k in license_['features'] for k in ('JAILS', 'VM'))
        else:
            # license could only have JAILS (containers) licensed or VM
            feature = 'JAILS' if instance_type == 'CONTAINER' else 'VM'
            return feature in license_['features']
