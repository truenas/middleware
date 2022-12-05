from catalog_validation.exceptions import ValidationErrors as CatalogValidationErrors

from middlewared.service import ValidationErrors


def check_errors(func: callable, *args, **kwargs):
    verrors = ValidationErrors()
    try:
        func(*args, **kwargs)
    except CatalogValidationErrors as e:
        verrors.extend(e)
    verrors.check()
