import logging

from middlewared.service import accepts, private, ServicePartBase

logger = logging.getLogger(__name__)


class ImportDiskBase(ServicePartBase):

    @private
    async def import_disk_kernel_module_context_manager(self, fs_type):
        raise NotImplementedError()

    @private
    async def import_disk_mount_fs_context_manager(self, device, src, fs_type, fs_options):
        raise NotImplementedError()

    @accepts()
    def import_disk_msdosfs_locales(self):
        """
        Get a list of locales for msdosfs type to be used in `pool.import_disk`.
        """
        raise NotImplementedError()
