from middlewared.service import accepts, Service


class SystemService(Service):

    @accepts()
    async def required_crash_kernel_memory(self):
        """
        Returns memory required for crash kernel to function in megabytes
        """
        # (memory in kb) / 16 / 1024 / 1024
        # For every 4KB of physical memory, we should allocate 2 bits to the crash kernel
        # In other words, for every 16KB of memory we allocate 1 byte.
        # https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/7/html/
        # kernel_administration_guide/kernel_crash_dump_guide#sect-kdump-memory-requirements
        #
        # We should test this on systems with higher memory as there are contradicting
        # docs - https://www.suse.com/support/kb/doc/?id=000016171
        current_mem = (await self.middleware.call('system.info'))['physmem'] / 1024
        return 256 + round(current_mem / 16 / 1024 / 1024)
