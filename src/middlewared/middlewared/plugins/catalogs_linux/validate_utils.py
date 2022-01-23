from catalog_validation.exceptions import ValidationErrors as CatalogValidationErrors
from catalog_validation.validation import validate_catalog_item, validate_catalog_item_version

from middlewared.service import ValidationErrors


def check_errors(func: callable, *args, **kwargs):
    verrors = ValidationErrors()
    try:
        func(*args, **kwargs)
    except CatalogValidationErrors as e:
        verrors.extend(e)
    verrors.check()


def validate_item(path: str, schema: dict, validate_versions: bool = True):
    check_errors(validate_catalog_item, path, schema, validate_versions)


def validate_item_version(path: str, schema: dict):
    check_errors(validate_catalog_item_version, path, schema)
