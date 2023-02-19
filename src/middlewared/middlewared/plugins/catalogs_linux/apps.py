from middlewared.schema import Bool, Dict, List, Str
from middlewared.service import filterable, filterable_returns, Service
from middlewared.utils import filter_list


class AppService(Service):

    @filterable
    @filterable_returns(Dict(
        'available_apps',
        Bool('healthy', required=True),
        List('categories', required=True),
        Str('name', required=True),
        Str('title', required=True),
        Str('description', required=True),
        Str('app_readme', required=True),
        Str('location', required=True),
        Str('healthy_error', required=True, null=True),
        Str('latest_version', required=True),
        Str('latest_app_version', required=True),
        Str('icon_url', required=True),
        Str('train', required=True),
        Str('catalog', required=True),
    ))
    def available(self, filters, options):
        results = []

        return filter_list(results, filters, options)
