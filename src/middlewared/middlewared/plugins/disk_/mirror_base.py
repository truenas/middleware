from middlewared.service import private, ServicePartBase


class DiskMirrorBase(ServicePartBase):

    mirror_base = {
        'name': None,
        'config_type': None,
        'path': None,
        'providers': [],  # actual partitions
    }

    @private
    async def get_mirrors(self):
        raise NotImplementedError()
