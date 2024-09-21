from middlewared.schema import accepts, Bool, Datetime, Dict, List, Ref, returns, Str
from middlewared.service import filterable, filterable_returns, Service
from middlewared.utils import filter_list


class AppService(Service):

    class Config:
        cli_namespace = 'app'

    @filterable(roles=['CATALOG_READ'])
    @filterable_returns(Ref('available_apps'))
    async def latest(self, filters, options):
        """
        Retrieve latest updated apps.
        """
        return filter_list(
            await self.middleware.call(
                'app.available', [
                    ['last_update', '!=', None], ['name', '!=', 'ix-app'],
                ], {'order_by': ['-last_update']}
            ), filters, options
        )

    @filterable(roles=['CATALOG_READ'])
    @filterable_returns(Dict(
        'available_apps',
        Bool('healthy', required=True),
        Bool('installed', required=True),
        Bool('recommended', required=True),
        Datetime('last_update', required=True),
        List('capabilities', required=True),
        List('run_as_context', required=True),
        List('categories', required=True),
        List('maintainers', required=True),
        List('tags', required=True),
        List('screenshots', required=True, items=[Str('screenshot')]),
        List('sources', required=True, items=[Str('source')]),
        Str('name', required=True),
        Str('title', required=True),
        Str('description', required=True),
        Str('app_readme', required=True),
        Str('location', required=True),
        Str('healthy_error', required=True, null=True),
        Str('home', required=True),
        Str('latest_version', required=True),
        Str('latest_app_version', required=True),
        Str('latest_human_version', required=True),
        Str('icon_url', null=True, required=True),
        Str('train', required=True),
        Str('catalog', required=True),
        register=True,
        # We do this because if we change anything in catalog.json, even older releases will
        # get this new field and different roles will start breaking due to this
        additional_attrs=True,
    ))
    def available(self, filters, options):
        """
        Retrieve all available applications from all configured catalogs.
        """
        if not self.middleware.call_sync('catalog.synced'):
            self.middleware.call_sync('catalog.sync').wait_sync()

        results = []
        installed_apps = [
            (app['metadata']['name'], app['metadata']['train'])
            for app in self.middleware.call_sync('app.query')
        ]

        catalog = self.middleware.call_sync('catalog.config')
        for train, train_data in self.middleware.call_sync('catalog.apps').items():
            if train not in catalog['preferred_trains']:
                continue

            for app_data in train_data.values():
                results.append({
                    'catalog': catalog['label'],
                    'installed': (app_data['name'], train) in installed_apps,
                    'train': train,
                    **app_data,
                })

        return filter_list(results, filters, options)

    @accepts(roles=['CATALOG_READ'])
    @returns(List(items=[Str('category')]))
    async def categories(self):
        """
        Retrieve list of valid categories which have associated applications.
        """
        return sorted(list(await self.middleware.call('catalog.retrieve_mapped_categories')))

    @accepts(Str('app_name'), Str('train'), roles=['CATALOG_READ'])
    @returns(List(items=[Ref('available_apps')]))
    def similar(self, app_name, train):
        """
        Retrieve applications which are similar to `app_name`.
        """
        available_apps = self.available()
        app = filter_list(available_apps, [['name', '=', app_name], ['train', '=', train]], {'get': True})
        similar_apps = {}

        # Calculate the number of common categories/tags between app and other apps
        app_categories = set(app['categories'])
        app_tags = set(app['tags'])
        app_similarity = {}

        for to_check_app in available_apps:
            if all(to_check_app[k] == app[k] for k in ('name', 'catalog', 'train')):
                continue

            common_categories = set(to_check_app['categories']).intersection(app_categories)
            common_tags = set(to_check_app['tags']).intersection(app_tags)
            similarity_score = len(common_categories) + len(common_tags)
            if similarity_score:
                app_similarity[to_check_app['name']] = similarity_score
                similar_apps[to_check_app['name']] = to_check_app

        # Sort apps based on the similarity score in descending order
        sorted_apps = sorted(app_similarity.keys(), key=lambda x: app_similarity[x], reverse=True)

        return [similar_apps[app] for app in sorted_apps]
