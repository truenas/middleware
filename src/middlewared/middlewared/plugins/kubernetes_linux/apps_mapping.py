import json
import jsonschema
import os

from middlewared.service import Service


MAPPING_SCHEMA = {
    'type': 'object',
    'properties': {
        'apps': {
            'type': 'array',
            'items': {'type': 'string'},
        },
        'services': {
            'type': 'object',
            'additionalProperties': False,
        },
    },
}


class KubernetesAppMappingService(Service):

    FILENAME = 'apps_mapping.json'
    MAPPING = None

    class Config:
        namespace = 'k8s.app.mapping'
        private = True

    def mapping_file_path(self):
        return os.path.join(
            '/mnt', self.middleware.call_sync('kubernetes.config')['dataset'], self.FILENAME
        )

    def setup(self):
        if not self.middleware.call_sync('kubernetes.validate_k8s_setup', False):
            return False

        mapping = {'apps': [], 'services': {}}
        try:
            with open(self.mapping_file_path(), 'r') as f:
                mapping = json.loads(f.read())
            jsonschema.validate(mapping, MAPPING_SCHEMA)
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, jsonschema.ValidationError):
            self.logger.error(
                'Malformed %r app mapping file found, re-creating', self.mapping_file_path(), exc_info=True
            )

        mapping['apps'] = [app['id'] for app in self.middleware.call_sync('chart.release.query')]
        # TODO: Services when added should also remove apps which are no longer there
        #  also we should do appropriate handling for services when added
        self.MAPPING = mapping

        self.write_to_file()
        self.register_services()

        return True

    def write_to_file(self):
        with open(self.mapping_file_path(), 'w') as f:
            f.write(json.dumps(self.MAPPING))

    def safe_setup(self):
        return self.setup() if self.MAPPING is None else True

    def _check(func):
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs) if self.safe_setup() else None
        return wrapper

    @_check
    def add_app(self, app):
        if app not in self.MAPPING['apps']:
            self.MAPPING['apps'].append(app)
            self.write_to_file()

    @_check
    def remove_app(self, app):
        if app in self.MAPPING['apps']:
            self.MAPPING['apps'].remove(app)
            # TODO: Remove this from services as well
            self.write_to_file()

    @_check
    def register_services(self):
        # TODO: Let's do this later once we know how mdns integration looks like
        pass

    @_check
    def unregister_services(self):
        # TODO: Let's do this later once we know how mdns integration looks like
        pass


async def app_post_create_hook(middleware, app):
    await middleware.call('k8s.app.mapping.add_app', app['id'])


async def app_post_delete_hook(middleware, app):
    await middleware.call('k8s.app.mapping.remove_app', app)


async def setup(middleware):
    await middleware.call('k8s.app.mapping.setup')
    middleware.register_hook('app.post_create', app_post_create_hook, sync=True)
    middleware.register_hook('app.post_delete', app_post_delete_hook, sync=True)
