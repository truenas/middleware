import re

from catalog_reader.app import get_app_version_details as get_catalog_app_version_details

from middlewared.plugins.update_.utils import can_update
from middlewared.utils import sw_info


RE_VERSION_PATTERN = re.compile(r'(\d{2}\.\d{2}(?:\.\d)*)')  # We are only interested in XX.XX here


def get_item_default_values(version_details: dict) -> dict:
    # FIXME: This needs to be done obviously
    return {}
    return construct_schema(version_details, {}, False)['new_values']


def custom_scale_version_checks(min_scale_version: str, max_scale_version: str, system_scale_version: str) -> str:
    if not (normalized_system_version := RE_VERSION_PATTERN.findall(system_scale_version)):
        return 'Unable to determine your TrueNAS system version'

    normalized_system_version = normalized_system_version[0]

    if min_scale_version and min_scale_version != normalized_system_version and not can_update(
        min_scale_version, normalized_system_version
    ):
        return (f'Your TrueNAS system version ({normalized_system_version}) is less than the minimum version '
                f'({min_scale_version}) required by this application.')

    if max_scale_version and max_scale_version != normalized_system_version and not can_update(
        normalized_system_version, max_scale_version
    ):
        return (f'Your TrueNAS system version ({normalized_system_version}) is greater than the maximum version '
                f'({max_scale_version}) required by this application.')

    return ''


def min_max_scale_version_check_update_impl(version_details: dict, check_supported_key: bool = True) -> str:
    # `check_supported_key` is used because when catalog validation returns the data it only checks the
    # missing features and based on that makes the decision. So if something is not already supported
    # we do not want to validate minimum scale version in that case. However, when we want to report to
    # the user as to why exactly the app version is not supported, we need to be able to make that distinction
    system_scale_version = sw_info()['version']
    min_scale_version = version_details.get('chart_metadata', {}).get('annotations', {}).get('min_scale_version')
    max_scale_version = version_details.get('chart_metadata', {}).get('annotations', {}).get('max_scale_version')
    if (
        version_details.get('healthy', True) and (not check_supported_key or version_details['supported'])
        and (min_scale_version or max_scale_version)
    ):
        try:
            if any(k in system_scale_version for k in ('MASTER', 'INTERNAL', 'CUSTOM')):
                return custom_scale_version_checks(min_scale_version, max_scale_version, system_scale_version)
            else:
                if (
                    min_scale_version and min_scale_version != system_scale_version and
                    not can_update(min_scale_version, system_scale_version)
                ):
                    return (f'Your TrueNAS system version ({system_scale_version}) is less than the minimum version '
                            f'({min_scale_version}) required by this application.')

                if (
                    max_scale_version and system_scale_version != max_scale_version and
                    not can_update(system_scale_version, max_scale_version)
                ):
                    return (f'Your TrueNAS system version ({system_scale_version}) is greater than the maximum version '
                            f'({max_scale_version}) required by this application.')
        except Exception:
            # In case invalid version string is specified we don't want a traceback here
            # let's just explicitly not support the app version in question
            return 'Unable to complete TrueNAS system version compatibility checks'

    return ''


def minimum_scale_version_check_update(version_details: dict) -> dict:
    version_details['supported'] = not bool(min_max_scale_version_check_update_impl(version_details))
    return version_details


def get_app_version_details(version_path: str, questions_context: dict) -> dict:
    return minimum_scale_version_check_update(get_catalog_app_version_details(version_path, questions_context, {
        'default_values_callable': get_item_default_values,
    }))
