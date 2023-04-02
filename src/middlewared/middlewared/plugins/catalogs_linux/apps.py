from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import filterable, filterable_returns, Service
from middlewared.utils import filter_list
from middlewared.validators import Range


class AppService(Service):

    class Config:
        cli_namespace = 'app'

    @accepts(Int('limit', default=10, validators=[Range(min=1)]))
    @returns(Ref('available_apps'))
    async def latest(self, limit):
        """
        Retrieve latest updated apps limiting the number by specifying `limit`.
        """
        return await self.middleware.call(
            'app.available', [['last_update', '!=', None]], {'order_by': ['-last_update'], 'limit': limit}
        )

    @filterable
    @filterable_returns(Dict(
        'available_apps',
        Bool('healthy', required=True),
        Bool('installed', required=True),
        List('categories', required=True),
        Str('name', required=True),
        Str('title', required=True),
        Str('description', required=True),
        Str('app_readme', required=True),
        Str('location', required=True),
        Str('healthy_error', required=True, null=True),
        Str('last_update', required=True),
        Str('latest_version', required=True),
        Str('latest_app_version', required=True),
        Str('icon_url', required=True),
        Str('train', required=True),
        Str('catalog', required=True),
        register=True
    ))
    def available(self, filters, options):
        """
        Retrieve all available applications from all configured catalogs.
        """
        if not self.middleware.call_sync('catalog.synced'):
            self.middleware.call_sync('catalog.initiate_first_time_sync')

        results = []
        installed_apps = [
            (app['chart_metadata']['name'], app['catalog'], app['catalog_train'])
            for app in self.middleware.call_sync('chart.release.query')
        ]

        for catalog in self.middleware.call_sync('catalog.query'):
            for train, train_data in self.middleware.call_sync('catalog.items', catalog['label']).items():
                for app_data in train_data.values():
                    results.append({
                        'catalog': catalog['label'],
                        'installed': (app_data['name'], catalog['label'], train) in installed_apps,
                        'train': train,
                        **app_data,
                    })

        return filter_list(results, filters, options)

    @accepts()
    @returns(List(items=[Str('category')]))
    async def categories(self):
        """
        Retrieve list of valid categories which have associated applications.
        """
        return sorted(list(await self.middleware.call('catalog.retrieve_mapped_categories')))
