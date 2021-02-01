import errno
import os

from catalog_validation.validation import validate_catalog, validate_catalog_item, validate_catalog_item_version

from middlewared.service import CallError, private, Service, ValidationErrors


class CatalogService(Service):

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
        except ValidationErrors as e:
            verrors.extend(e)
        verrors.check()

    @private
    def validate_catalog_item(self, path, schema, validate_versions=True):
        self.check_errors(validate_catalog_item, path, schema, validate_versions)

    @private
    def validate_catalog_item_version(self, path, schema):
        self.check_errors(validate_catalog_item_version, path, schema)
