from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service


class VMService(Service):

    class Config:
        cli_namespace = 'service.vm'

    @accepts()
    @returns(Dict(additional_attrs=True))
    async def profiles(self):
        """
        Returns a dictionary of defaults for different VM guest types.
        """
        return {
            'WINDOWS': {
                'trusted_platform_module': True,
                'memory': 8192,
                'cores': 2,
                'bootloader_ovmf': 'OVMF_CODE_4M.fd',
            },
            'LINUX': {
                'memory': 8192,
                'cores': 2,
            },
            'OTHERS': {
                'memory': 8192,
                'cores': 2,
            },
        }
