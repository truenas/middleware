from middlewared.service import private, ServicePartBase


class SEDBase(ServicePartBase):

    @private
    async def unlock_ata_security(self, devname, _advconfig, password):
        raise NotImplementedError
