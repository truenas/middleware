from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetChecksumChoicesArgs, PoolDatasetChecksumChoicesResult, PoolDatasetCompressionChoicesArgs,
    PoolDatasetCompressionChoicesResult, PoolDatasetEncryptionAlgorithmChoicesArgs,
    PoolDatasetEncryptionAlgorithmChoicesResult, PoolDatasetRecommendedZvolBlocksizeArgs,
    PoolDatasetRecommendedZvolBlocksizeResult
)
from middlewared.service import Service

from .utils import ZFS_CHECKSUM_CHOICES, ZFS_COMPRESSION_ALGORITHM_CHOICES, ZFS_ENCRYPTION_ALGORITHM_CHOICES


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetChecksumChoicesArgs, PoolDatasetChecksumChoicesResult, roles=['DATASET_READ'])
    async def checksum_choices(self):
        """
        Retrieve checksums supported for ZFS dataset.
        """
        return {v: v for v in ZFS_CHECKSUM_CHOICES if v != 'OFF'}

    @api_method(PoolDatasetCompressionChoicesArgs, PoolDatasetCompressionChoicesResult, roles=['DATASET_READ'])
    async def compression_choices(self):
        """
        Retrieve compression algorithm supported by ZFS.
        """
        return {v: v for v in ZFS_COMPRESSION_ALGORITHM_CHOICES}

    @api_method(
        PoolDatasetEncryptionAlgorithmChoicesArgs,
        PoolDatasetEncryptionAlgorithmChoicesResult,
        roles=['DATASET_READ']
    )
    async def encryption_algorithm_choices(self):
        """
        Retrieve encryption algorithms supported for ZFS dataset encryption.
        """
        return {v: v for v in ZFS_ENCRYPTION_ALGORITHM_CHOICES}

    @api_method(
        PoolDatasetRecommendedZvolBlocksizeArgs,
        PoolDatasetRecommendedZvolBlocksizeResult,
        roles=['DATASET_READ']
    )
    async def recommended_zvol_blocksize(self, pool):
        """
        Helper method to get recommended size for a new zvol (dataset of type VOLUME).

        .. examples(websocket)::

          Get blocksize for pool "tank".

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.recommended_zvol_blocksize",
                "params": ["tank"]
            }
        """
        pool = await self.middleware.call('pool.query', [['name', '=', pool]], {'get': True})

        """
        Cheatsheat for blocksizes is as follows:
        2w/3w mirror = 16K
        3wZ1, 4wZ2, 5wZ3 = 16K
        4w/5wZ1, 5w/6wZ2, 6w/7wZ3 = 32K
        6w/7w/8w/9wZ1, 7w/8w/9w/10wZ2, 8w/9w/10w/11wZ3 = 64K
        10w+Z1, 11w+Z2, 12w+Z3 = 128K

        If the zpool was forcefully created with mismatched
        vdev geometry (i.e. 3wZ1 and a 5wZ1) then we calculate
        the blocksize based on the largest vdev of the zpool.
        """
        maxdisks = 1
        for vdev in pool['topology']['data']:
            if vdev['type'] == 'RAIDZ1':
                disks = len(vdev['children']) - 1
            elif vdev['type'] == 'RAIDZ2':
                disks = len(vdev['children']) - 2
            elif vdev['type'] == 'RAIDZ3':
                disks = len(vdev['children']) - 3
            elif vdev['type'] == 'MIRROR':
                disks = maxdisks
            else:
                disks = len(vdev['children'])

            if disks > maxdisks:
                maxdisks = disks

        return f'{max(16, min(128, 2 ** ((maxdisks * 8) - 1).bit_length()))}K'
