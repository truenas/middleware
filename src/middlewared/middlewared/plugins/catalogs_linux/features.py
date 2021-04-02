import errno
import json
import os

from middlewared.service import CallError, private, Service


SUPPORTED_FEATURES = {
    'normalize/interfaceConfiguration',
    'normalize/ixVolume',
    'definitions/certificate',
    'definitions/certificateAuthority',
    'definitions/interface',
    'definitions/gpuConfiguration',
    'definitions/timezone',
    'definitions/nodeIP',
    'validations/containerImage',
    'validations/nodePort',
}


class CatalogService(Service):

    @private
    async def version_supported(self, version_details):
        return not bool(set(version_details['required_features']) - SUPPORTED_FEATURES)

    @private
    def get_feature_map(self, cache=True):
        if cache and self.middleware.call_sync('cache.has_key', 'catalog_feature_map'):
            return self.middleware.call_sync('cache.get', 'catalog_feature_map')

        catalog = self.middleware.call_sync(
            'catalog.get_instance', self.middleware.call_sync('catalog.official_catalog_label')
        )

        path = os.path.join(catalog['location'], 'features_capability.json')
        if not os.path.exists(path):
            raise CallError('Unable to retrieve feature capability mapping for SCALE versions', errno=errno.ENOENT)

        with open(path, 'r') as f:
            mapping = json.loads(f.read())

        self.middleware.call_sync('cache.put', 'catalog_feature_map', mapping, 86400)

        return mapping

    @private
    async def version_supported_error_check(self, version_details):
        if version_details['supported']:
            return

        if not version_details['healthy']:
            raise CallError(version_details['healthy_error'])

        missing_features = set(version_details['required_features']) - SUPPORTED_FEATURES
        try:
            mapping = await self.middleware.call('catalog.get_feature_map')
        except Exception as e:
            self.logger.error('Unable to retrieve feature mapping for SCALE versions: %s', e)
            mapping = {}

        error_str = 'Catalog item version is not supported due to following missing features:\n'
        for index, feature in enumerate(missing_features):
            train_message = ''
            for k, v in mapping.get(feature, {}).items():
                train_message += f'\nFor {k.capitalize()!r} train:\nMinimum SCALE version: {v["min"]}\n'
                if v.get('max'):
                    train_message += f'Maximum SCALE version: {v["max"]}'
                else:
                    train_message += f'Maximum SCALE version: Latest available {k.capitalize()!r} release'

            error_str += f'{index + 1}) {feature}{f"{train_message}" if train_message else ""}\n\n'

        raise CallError(error_str)
