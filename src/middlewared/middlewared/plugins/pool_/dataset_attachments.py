from middlewared.api import api_method
from middlewared.api.current import PoolDatasetAttachmentsArgs, PoolDatasetAttachmentsResult
from middlewared.service import Service


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetAttachmentsArgs, PoolDatasetAttachmentsResult, roles=['DATASET_READ'])
    async def attachments(self, oid):
        """
        Return a list of services dependent of this dataset.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.

        Example return value::

            [
              {
                "type": "NFS Share",
                "service": "nfs",
                "attachments": ["/mnt/tank/work"]
              }
            ]
        """
        return await self.call2(self.s.zfs.resource.attachments, oid)
