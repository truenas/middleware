from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetChecksumChoicesArgs,
    PoolDatasetChecksumChoicesResult,
    PoolDatasetCompressionChoicesArgs,
    PoolDatasetCompressionChoicesResult,
    PoolDatasetRecommendedZvolBlocksizeArgs,
    PoolDatasetRecommendedZvolBlocksizeResult,
)
from middlewared.service import Service


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetChecksumChoicesArgs, PoolDatasetChecksumChoicesResult, roles=['DATASET_READ'])
    async def checksum_choices(self):
        """
        Retrieve checksums supported for ZFS dataset.
        """
        return await self.call2(self.s.zfs.resource.checksum_choices)

    @api_method(PoolDatasetCompressionChoicesArgs, PoolDatasetCompressionChoicesResult, roles=['DATASET_READ'])
    async def compression_choices(self):
        """
        Retrieve compression algorithm supported by ZFS.
        """
        return await self.call2(self.s.zfs.resource.compression_choices)

    @api_method(
        PoolDatasetRecommendedZvolBlocksizeArgs,
        PoolDatasetRecommendedZvolBlocksizeResult,
        roles=['DATASET_READ']
    )
    async def recommended_zvol_blocksize(self, pool):
        """
        Helper method to get recommended size for a new zvol (dataset of type VOLUME).

        Get blocksize for pool "tank"::

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "pool.dataset.recommended_zvol_blocksize",
                "params": ["tank"]
            }
        """
        return await self.call2(self.s.zfs.resource.recommended_zvol_blocksize, pool)
