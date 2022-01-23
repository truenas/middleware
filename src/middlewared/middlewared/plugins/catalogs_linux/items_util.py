from middlewared.plugins.chart_releases_linux.schema import construct_schema


def get_item_default_values(version_details: dict) -> dict:
    return construct_schema(version_details, {}, False)['new_values']
