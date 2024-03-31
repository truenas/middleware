from middlewared.schema import accepts, Bool, Dict, returns, Str
from middlewared.service import private, Service


class FailoverService(Service):

    @private
    async def retrieve_boot_ids(self):
        return {
            await self.middleware.call('failover.node'): await self.middleware.call('system.boot_id'),
            await self.middleware.call(
                'failover.call_remote', 'failover.node', [], {'raise_connect_error': False}
            ): await self.middleware.call(
                'failover.call_remote', 'system.boot_id', [], {'raise_connect_error': False}
            ),
        }

    @accepts()
    @returns(Dict(
        Bool('reboot_required'),
        Bool('node_a_reboot_required'),
        Bool('node_b_reboot_required'),
        Str('reason'),
    ))
    async def reboot_required(self):
        """
        Returns whether a reboot is required for failover/security system configuration changes to take effect.
        """
        return await self.check_reboot_required()

    @private
    async def check_reboot_required(self):
        fips_change_info = await self.middleware.call('keyvalue.get', 'fips_toggled', False)
        if not fips_change_info:
            return {
                'reboot_required': False,
                'node_a_reboot_required': False,
                'node_b_reboot_required': False,
                'reason': 'No reboot required',
            }

        existing_boot_ids = await self.retrieve_boot_ids()
        info = {
            'reason': 'No reboot required',
            # We retrieve A/B safely just to be sure that we don't have any issues
            # Not sure what the best way to handle it would be if we were not able to connect to remote
            'node_a_reboot_required': existing_boot_ids.get('A') == fips_change_info.get('A'),
            'node_b_reboot_required': existing_boot_ids.get('B') == fips_change_info.get('B'),
        }
        if info['node_a_reboot_required'] or info['node_b_reboot_required']:
            info.update({
                'reboot_required': True,
                'reason': 'Reboot required for FIPS configuration change to take effect',
            })
        else:
            await self.middleware.call('keyvalue.delete', 'fips_toggled')

        return info
