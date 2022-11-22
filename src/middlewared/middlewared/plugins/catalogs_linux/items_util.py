from catalog_validation.items.items_util import (
    get_item_details as get_catalog_item_details,
    get_item_version_details as get_catalog_item_version_details,
)

from middlewared.plugins.chart_releases_linux.schema import construct_schema


def get_item_default_values(version_details: dict) -> dict:
    return construct_schema(version_details, {}, False)['new_values']


def get_item_details(item_location: str, questions_context: dict, options: dict) -> dict:
    return get_catalog_item_details(item_location, questions_context, {
        **options,
        'default_values_callable': get_item_default_values,
    })


def get_item_version_details(version_path: str, questions_context: dict) -> dict:
    return get_catalog_item_version_details(version_path, questions_context, {
        'default_values_callable': get_item_default_values,
    })
