from middlewared.service import private, Service


SUPPORTED_FEATURES = {
    'normalize/interfaceConfiguration',
    'normalize/ixVolume',
    'definitions/interface',
    'validations/persistentVolumeClaims',
}


class CatalogService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def version_supported(self, version_details):
        return bool(version_details['required_features'] - SUPPORTED_FEATURES)
