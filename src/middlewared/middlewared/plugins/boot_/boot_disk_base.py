from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import private, ServicePartBase


class BootDiskBase(ServicePartBase):

    @accepts(
        Str('dev'),
        Dict(
            'options',
            Int('size'),
            Int('swap_size'),
        )
    )
    @private
    async def format(self, dev, options):
        """
        Format a given disk `dev` using the appropriate partition layout
        """
