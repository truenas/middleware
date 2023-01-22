import typing

from catalog_validation.items.items_util import (
    get_item_details as get_catalog_item_details,
    get_item_version_details as get_catalog_item_version_details,
)

from middlewared.plugins.chart_releases_linux.schema import construct_schema
from middlewared.plugins.update_.utils import can_update
from middlewared.utils import manifest_version


def get_item_default_values(version_details: dict) -> dict:
    return construct_schema(version_details, {}, False)['new_values']


def minimum_scale_version_check_update(version_details: dict) -> dict:
    version_details['supported'] = minimum_scale_version_check_update_impl(version_details)[0]
    return version_details


def minimum_scale_version_check_update_impl(
    version_details: dict, check_supported_key: bool = True
) -> typing.Tuple[bool, bool]:
    # `check_supported_key` is used because when catalog validation returns the data it only checks the
    # missing features and based on that makes the decision. So if something is not already supported
    # we do not want to validate minimum scale version in that case. However, when we want to report to
    # the user as to why exactly the app version is not supported, we need to be able to make that distinction
    if version_details['healthy'] and version_details['chart_metadata'].get('minimum_scale_version') and (
        not check_supported_key or version_details['supported']
    ):
        try:
            if manifest_version() != version_details['chart_metadata']['minimum_scale_version'] and not can_update(
                version_details['chart_metadata']['minimum_scale_version'], manifest_version()
            ):
                return False, False
        except Exception:
            # In case invalid version string is specified we don't want a traceback here
            # let's just explicitly not support the app version in question
            return False, True

    return True, False


def get_item_details(item_location: str, questions_context: dict, options: dict) -> dict:
    item_details = get_catalog_item_details(item_location, questions_context, {
        **options,
        'default_values_callable': get_item_default_values,
    })
    for version in item_details['versions'].values():
        minimum_scale_version_check_update(version)

    return item_details


def get_item_version_details(version_path: str, questions_context: dict, scale_version: str) -> dict:
    return minimum_scale_version_check_update(get_catalog_item_version_details(version_path, questions_context, {
        'default_values_callable': get_item_default_values,
    }))
