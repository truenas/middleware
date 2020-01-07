from middlewared.schema import accepts, Dict, Str, List
from middlewared.service import filterable, private, ServicePartBase


class DiskMirrorBase(ServicePartBase):

    mirror_base = {
        'name': None,
        'config_type': None,
        'path': None,
        'real_path': None,  # real path in case `path` is a symbolic link
        'encrypted_provider': None,
        'providers': [],  # actual partitions
        'is_swap_mirror': False,
    }

    @private
    @accepts(
        Str('name'),
        Dict(
            'create_mirror_options',
            Dict('extra', additional_attrs=True),
            List('paths', empty=False, required=True),
        )
    )
    async def create_mirror(self, name, options):
        raise NotImplementedError()

    @private
    async def destroy_mirror(self, name):
        raise NotImplementedError()

    @private
    @filterable
    async def get_mirrors(self, filters, options):
        raise NotImplementedError()
