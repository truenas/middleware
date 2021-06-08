import errno
import os

from catalog_validation.exceptions import ValidationErrors as CatalogValidationErrors
from catalog_validation.validation import validate_catalog, validate_catalog_item, validate_catalog_item_version

from middlewared.schema import returns, Str
from middlewared.service import accepts, CallError, private, Service, ValidationErrors


class CatalogService(Service):

    @accepts(Str('label'))
    @returns()
    async def validate(self, label):
        """
        Validates `label` catalog format which includes validating trains and applications with their versions.

        This does not test if an app version is valid in terms of kubernetes resources but instead ensures it has
        the correct format and files necessary for TrueNAS to use it.
        """
        catalog = await self.middleware.call('catalog.get_instance', label)
        await self.middleware.call('catalog.validate_catalog_from_path', catalog['location'])

    @private
    def validate_catalog_from_path(self, path):
        if not os.path.exists(path):
            raise CallError(f'{path!r} does not exist', errno=errno.ENOENT)

        self.check_errors(validate_catalog, path)

    @private
    def check_errors(self, func, *args, **kwargs):
        verrors = ValidationErrors()
        try:
            func(*args, **kwargs)
        except CatalogValidationErrors as e:
            verrors.extend(e)
        verrors.check()

    @private
    def validate_catalog_item(self, path, schema, validate_versions=True):
        self.check_errors(validate_catalog_item, path, schema, validate_versions)

    @private
    def validate_catalog_item_version(self, path, schema):
        self.check_errors(validate_catalog_item_version, path, schema)
