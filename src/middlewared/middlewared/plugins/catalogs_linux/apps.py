from middlewared.schema import accepts, Bool, Dict, List, returns, Str
from middlewared.service import filterable, filterable_returns, job, Service
from middlewared.utils import filter_list


class AppService(Service):

    class Config:
        cli_namespace = 'app'

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
        Str('latest_version', required=True),
        Str('latest_app_version', required=True),
        Str('icon_url', required=True),
        Str('train', required=True),
        Str('catalog', required=True),
    ))
    @job(lock='available_apps', lock_queue_size=1)
    def available(self, job, filters, options):
        """
        Retrieve all available applications from all configured catalogs.
        """
        results = []
        catalogs = self.middleware.call_sync('catalog.query')
        installed_apps = [
            (app['chart_metadata']['name'], app['catalog'], app['catalog_train'])
            for app in self.middleware.call_sync('chart.release.query')
        ]
        total_catalogs = len(catalogs)
        job.set_progress(5, 'Retrieving available apps from catalog(s)')

        for index, catalog in enumerate(catalogs):
            progress = 10 + ((index + 1 / total_catalogs) * 80)
            items_job = self.middleware.call_sync('catalog.items', catalog['label'])
            items_job.wait_sync()
            if items_job.error:
                job.set_progress(progress, f'Failed to retrieve apps from {catalog["label"]!r}')
                continue

            catalog_items = items_job.result
            for train, train_data in catalog_items.items():
                for app_data in train_data.values():
                    results.append({
                        'catalog': catalog['label'],
                        'installed': (app_data['name'], catalog['label'], train) in installed_apps,
                        'train': train,
                        **app_data,
                    })

            job.set_progress(progress, f'Completed retrieving apps from {catalog["label"]!r}')

        results = filter_list(results, filters, options)
        job.set_progress(100, 'Retrieved all available apps from all catalog(s)')
        return results

    @accepts()
    @returns(List(items=[Str('category')]))
    async def categories(self):
        """
        Retrieve list of valid categories which have associated applications.
        """
        return sorted(list(await self.middleware.call('catalog.retrieve_mapped_categories')))
