import contextlib
import errno
import shutil
import textwrap

from middlewared.schema import accepts, Dict, returns, Str
from middlewared.service import CallError, CRUDService, filterable, job
from middlewared.utils import filter_list
from middlewared.validators import Match, Range

from .ix_apps.lifecycle import add_context_to_values, get_current_app_config, update_app_config
from .ix_apps.path import get_installed_app_path, get_installed_app_version_path
from .ix_apps.query import list_apps
from .app_setup_utils import setup_install_app_dir
from .app_utils import get_version_in_use_of_app
from .compose_utils import compose_action
from .version_utils import get_latest_version_from_app_versions


class AppService(CRUDService):
    class Config:
        namespace = 'app'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app'
        private = True  # FIXME: Remove this once we have schema defined

    @filterable
    def query(self, filters, options):
        if not self.middleware.call_sync('docker.state.validate', False):
            return filter_list([], filters, options)

        kwargs = {}
        if len(filters) == 1 and filters[0][0] in ('id', 'name') and filters[0][1] == '=':
            kwargs = {'specific_app': filters[0][2]}

        return filter_list(list_apps(**kwargs), filters, options)

    @accepts(Str('app_name'))
    @returns(Dict('app_config', additional_attrs=True))
    def config(self, app_name):
        """
        Retrieve user specified configuration of `app_name`.
        """
        app = self.get_instance__sync(app_name)
        return get_current_app_config(app_name, app['version'])

    @accepts(
        Dict(
            'app_create',
            Dict('values', additional_attrs=True, private=True),
            Str('catalog_app', required=True),
            Str(
                'app_name', required=True, validators=[Match(
                    r'^[a-z]([-a-z0-9]*[a-z0-9])?$',
                    explanation=textwrap.dedent(
                        '''
                        Application name must have the following:
                        1) Lowercase alphanumeric characters can be specified
                        2) Name must start with an alphabetic character and can end with alphanumeric character
                        3) Hyphen '-' is allowed but not as the first or last character
                        e.g abc123, abc, abcd-1232
                        '''
                    )
                ), Range(min_=1, max_=40)]
            ),
            Str('train', default='stable'),
            Str('version', default='latest'),
        )
    )
    @job(lock=lambda args: f'app_create_{args[0]["app_name"]}')
    def do_create(self, job, data):
        self.middleware.call_sync('docker.state.validate')

        if self.query([['id', '=', data['app_name']]]):
            raise CallError(f'Application with name {data["app_name"]} already exists', errno=errno.EEXIST)

        app_name = data['app_name']
        complete_app_details = self.middleware.call_sync('catalog.get_app_details', data['catalog_app'], {
            'train': data['train'],
        })
        version = data['version']
        if version == 'latest':
            version = get_latest_version_from_app_versions(complete_app_details['versions'])

        if version not in complete_app_details['versions']:
            raise CallError(f'Version {version} not found in {data["item"]} app', errno=errno.ENOENT)

        app_version_details = complete_app_details['versions'][version]
        self.middleware.call_sync('catalog.version_supported_error_check', app_version_details)

        # The idea is to validate the values provided first and if it passes our validation test, we
        # can move forward with setting up the datasets and installing the catalog item
        new_values, context = self.middleware.call_sync(
            'app.schema.normalise_and_validate_values', app_version_details, data['values'], False,
            get_installed_app_path(app_name)
        )

        job.set_progress(25, 'Initial Validation completed')

        # Now that we have completed validation for the app in question wrt values provided,
        # we will now perform the following steps
        # 1) Create relevant dir for app
        # 2) Copy app version into app dir
        # 3) Have docker compose deploy the app in question
        try:
            setup_install_app_dir(app_name, app_version_details)
            new_values = add_context_to_values(app_name, new_values, install=True)
            update_app_config(app_name, version, new_values)
            job.set_progress(60, 'App installation in progress, pulling images')
            compose_action(app_name, version, 'up', force_recreate=True, remove_orphans=True)
        except Exception as e:
            job.set_progress(80, f'Failure occurred while installing {data["app_name"]!r}, cleaning up')
            with contextlib.suppress(Exception):
                self.delete_internal(app_name, version)
            raise e from None
        else:
            job.set_progress(100, f'{data["app_name"]!r} installed successfully')
            return self.get_instance__sync(app_name)

    @accepts(
        Str('app_name'),
        Dict(
            'app_update',
            Dict('values', additional_attrs=True, private=True),
        )
    )
    @job(lock=lambda args: f'app_update_{args[0]}')
    def do_update(self, job, app_name, data):
        app = self.get_instance__sync(app_name)
        config = get_current_app_config(app_name, app['version'])
        config.update(data['values'])
        # We use update=False because we want defaults to be populated again if they are not present in the payload
        # Why this is not dangerous is because the defaults will be added only if they are not present/configured for
        # the app in question
        app_version_details = self.middleware.call_sync(
            'catalog.app_version_details', get_installed_app_version_path(app_name, app['version'])
        ) | {'catalog_app_last_updated': app['catalog_app_last_updated']}  # FIXME: We should already have this

        new_values, context = self.middleware.call_sync(
            'app.schema.normalise_and_validate_values', app_version_details, data['values'], False,
            get_installed_app_path(app_name),
        )

        job.set_progress(25, 'Initial Validation completed')

        new_values = add_context_to_values(app_name, new_values, update=True)
        update_app_config(app_name, app['version'], new_values)
        job.set_progress(60, 'Configuration updated, updating docker resources')
        compose_action(app_name, app['version'], 'up', force_recreate=True, remove_orphans=True)

        job.set_progress(100, f'Update completed for {app_name!r}')
        return self.get_instance__sync(app_name)

    def delete_internal(self, app_name, version):
        compose_action(app_name, version, 'down', remove_orphans=True)
        shutil.rmtree(get_installed_app_path(app_name))

    @accepts(Str('app_name'))
    def do_delete(self, app_name):
        self.get_instance__sync(app_name)
        self.delete_internal(app_name, get_version_in_use_of_app(app_name))
        return True
