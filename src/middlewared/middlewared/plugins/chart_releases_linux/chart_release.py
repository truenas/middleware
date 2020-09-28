from middlewared.schema import accepts, Dict, Str
from middlewared.service import CallError, CRUDService


class ChartReleaseService(CRUDService):

    class Config:
        namespace = 'chart.release'

    @accepts(
        Dict(
            'chart_release_create',
            Dict('values', additional_attrs=True),
            Str('catalog', required=True),
            Str('item', required=True),
            Str('release_name', required=True),
            Str('train', default='charts'),
            Str('version', required=True),
        )
    )
    async def do_create(self, data):
        catalog = await self.middleware.call('catalog.get_instance', data['catalog'])
        if data['train'] not in catalog['trains']:
            raise CallError(f'Unable to locate "{data["train"]}" catalog train.')
        if data['item'] not in catalog['trains'][data['train']]:
            raise CallError(f'Unable to locate "{data["item"]}" catalog item.')
        if data['version'] not in catalog['trains'][data['train']][data['item']]['versions']:
            raise CallError(f'Unable to locate "{data["version"]}" catalog item version.')

        item_details = catalog['trains'][data['train']][data['item']]['versions'][data['version']]
        # The idea is to validate the values provided first and if it passes our validation test, we
        # can move forward with setting up the datasets and installing the catalog item
        await self.middleware.call('chart.release.validate_values', item_details, data)
        # TODO: Validate if the release name has not been already used, let's do that once we have query
        # in place
