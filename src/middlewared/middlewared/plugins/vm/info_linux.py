from middlewared.service import Service
from middlewared.utils import run

from .info_base import VMInfoBase


class VMService(Service, VMInfoBase):

    async def supports_virtualization(self):
        cp = await run(['kvm-ok'], check=False)
        return cp.returncode == 0

    def available_slots(self):
        raise NotImplementedError

    def flags(self):
        raise NotImplementedError

    async def get_console(self, id):
        raise NotImplementedError
