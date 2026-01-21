import errno
import json
import os

from apps_schema.features import FEATURES
from middlewared.service import CallError, private, Service

from .apps_util import min_max_scale_version_check_update_impl


class CatalogService(Service):

    @private
    def get_feature_map(self, cache=True):
        if cache:
            try:
                return self.middleware.call_sync('cache.get', 'catalog_feature_map', 'PERSISTENT')
            except KeyError:
                pass

        catalog = self.middleware.call_sync('catalog.config')

        path = os.path.join(catalog['location'], 'features_capability.json')
        if not os.path.exists(path):
            raise CallError('Unable to retrieve feature capability mapping for SCALE versions', errno=errno.ENOENT)

        with open(path, 'r') as f:
            mapping = json.loads(f.read())

        self.middleware.call_sync('cache.put', 'catalog_feature_map', mapping, 86400, 'PERSISTENT')

        return mapping

    @private
    async def version_supported_error_check(self, version_details):
        if version_details['supported']:
            return

        if not version_details['healthy']:
            raise CallError(version_details['healthy_error'])

        # There will be 2 scenarios now because of which a version might not be supported
        # 1) Missing features
        # 2) Minimum/maximum scale version check specified

        error_str = ''
        missing_features = set(version_details['required_features']) - set(FEATURES)
        if missing_features:
            error_str = await self.missing_feature_error_message(missing_features)

        if err := min_max_scale_version_check_update_impl(version_details, False):
            prefix = '\n\n' if error_str else ''
            error_str = f'{error_str}{prefix}{" Also" if error_str else ""}{err}'

        raise CallError(error_str)

    @private
    async def missing_feature_error_message(self, missing_features):
        try:
            mapping = await self.middleware.call('catalog.get_feature_map')
        except Exception as e:
            self.logger.error('Unable to retrieve feature mapping for SCALE versions: %s', e)
            mapping = {}

        error_str = 'Catalog app version is not supported due to following missing features:\n'
        for index, feature in enumerate(missing_features):
            train_message = ''
            for k, v in mapping.get(feature, {}).items():
                train_message += f'\nFor {k.capitalize()!r} train:\nMinimum SCALE version: {v["min"]}\n'
                if v.get('max'):
                    train_message += f'Maximum SCALE version: {v["max"]}'
                else:
                    train_message += f'Maximum SCALE version: Latest available {k.capitalize()!r} release'

            error_str += f'{index + 1}) {feature}{f"{train_message}" if train_message else ""}\n\n'

        return error_str
