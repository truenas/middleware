import errno
import os

from catalog_validation.validation import validate_catalog

from middlewared.service import CallError, private, Service, ValidationErrors


class CatalogService(Service):

    @private
    async def validate_catalog_from_path(self, path):
        if not os.path.exists(path):
            raise CallError(f'{path!r} does not exist', errno=errno.ENOENT)

        verrors = ValidationErrors()
        try:
            validate_catalog(path)
        except ValidationErrors as e:
            verrors.extend(e)

        verrors.check()
