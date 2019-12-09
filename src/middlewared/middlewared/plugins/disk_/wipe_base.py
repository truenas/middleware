from middlewared.schema import accepts, Bool, Str
from middlewared.service import job, private, ServicePartBase


class WipeDiskBase(ServicePartBase):

    @private
    async def wipe_quick(self, dev, size=None):
        """
        Perform a quick wipe of a disk `dev` by the first few and last few megabytes.

        `dev` can be a complete disk or a partition
        """

    @accepts(
        Str('dev'),
        Str('mode', enum=['QUICK', 'FULL', 'FULL_RANDOM']),
        Bool('synccache', default=True),
    )
    @job(lock=lambda args: args[0])
    async def wipe(self, job, dev, mode, sync):
        """
        Performs a wipe of a disk `dev`.
        It can be of the following modes:
          - QUICK: clean the first few and last megabytes of every partition and disk
          - FULL: write whole disk with zero's
          - FULL_RANDOM: write whole disk with random bytes
        """
