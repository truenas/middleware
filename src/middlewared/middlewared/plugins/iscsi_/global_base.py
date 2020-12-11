from middlewared.service import filterable, private, ServicePartBase


class GlobalActionsBase(ServicePartBase):

    @filterable
    async def sessions(self, filters, options):
        """
       Get a list of currently running iSCSI sessions. This includes initiator and target names
       and the unique connection IDs.
       """

    @private
    async def terminate_luns_for_pool(self, pool_name):
        raise NotImplementedError()
