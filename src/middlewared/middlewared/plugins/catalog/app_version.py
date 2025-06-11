import errno
import os
import stat

from catalog_reader.train_utils import get_train_path

from middlewared.api import api_method
from middlewared.api.current import CatalogGetAppDetailsArgs, CatalogGetAppDetailsResult
from middlewared.service import CallError, Service

from .apps_util import get_app_details


class CatalogService(Service):

    class Config:
        cli_namespace = 'app.catalog'

    @api_method(CatalogGetAppDetailsArgs, CatalogGetAppDetailsResult, roles=['CATALOG_READ'])
    def get_app_details(self, app_name, options):
        """
        Retrieve information of `app_name` `app_version_details.catalog` catalog app.
        """
        catalog = self.middleware.call_sync('catalog.config')
        app_location = os.path.join(get_train_path(catalog['location']), options['train'], app_name)
        try:
            if not stat.S_ISDIR(os.stat(app_location).st_mode):
                raise CallError(f'{app_location!r} must be a directory')
        except FileNotFoundError:
            raise CallError(f'Unable to locate {app_name!r} at {app_location!r}', errno=errno.ENOENT)

        train_data = self.middleware.call_sync('catalog.apps', {
            'retrieve_all_trains': False,
            'trains': [options['train']],
        })
        if options['train'] not in train_data:
            raise CallError(f'Unable to locate {options["train"]!r} train')
        elif app_name not in train_data[options['train']]:
            raise CallError(f'Unable to locate {app_name!r} app in {options["train"]!r} train')

        questions_context = self.middleware.call_sync('catalog.get_normalized_questions_context')

        app_details = get_app_details(app_location, train_data[options['train']][app_name], questions_context)
        recommended_apps = self.middleware.call_sync('catalog.retrieve_recommended_apps')
        if options['train'] in recommended_apps and app_name in recommended_apps[options['train']]:
            app_details['recommended'] = True

        return app_details
