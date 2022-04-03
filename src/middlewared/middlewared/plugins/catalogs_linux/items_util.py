import markdown
import os
import yaml

from pkg_resources import parse_version

from middlewared.plugins.chart_releases_linux.schema import construct_schema
from middlewared.service import ValidationErrors

from .features import version_supported
from .questions_utils import normalise_questions
from .validate_utils import validate_item, validate_item_version


ITEM_KEYS = ['icon_url']


def get_item_default_values(version_details: dict) -> dict:
    return construct_schema(version_details, {}, False)['new_values']


def get_item_details(item_location: str, questions_context: dict, options: dict) -> dict:
    item = item_location.rsplit('/', 1)[-1]
    train = item_location.rsplit('/', 2)[-2]

    retrieve_versions = options.get('retrieve_versions', True)
    item_data = {
        'name': item,
        'categories': [],
        'app_readme': None,
        'location': item_location,
        'healthy': False,  # healthy means that each version the item hosts is valid and healthy
        'healthy_error': None,  # An error string explaining why the item is not healthy
        'versions': {},
        'latest_version': None,
        'latest_app_version': None,
        'latest_human_version': None,
    }

    schema = f'{train}.{item}'
    try:
        validate_item(item_location, schema, False)
    except ValidationErrors as verrors:
        item_data['healthy_error'] = f'Following error(s) were found with {item!r}:\n'
        for verror in verrors:
            item_data['healthy_error'] += f'{verror[0]}: {verror[1]}'

        # If the item format is not valid - there is no point descending any further into versions
        if not retrieve_versions:
            item_data.pop('versions')
        return item_data

    item_data.update(get_item_details_impl(item_location, schema, questions_context, {
        'retrieve_latest_version': not retrieve_versions,
    }))
    unhealthy_versions = []
    for k, v in sorted(item_data['versions'].items(), key=lambda v: parse_version(v[0]), reverse=True):
        if not v['healthy']:
            unhealthy_versions.append(k)
        else:
            if not item_data['app_readme']:
                item_data['app_readme'] = v['app_readme']
            if not item_data['latest_version']:
                item_data['latest_version'] = k
                item_data['latest_app_version'] = v['chart_metadata'].get('appVersion')
                item_data['latest_human_version'] = ''
                if item_data['latest_app_version']:
                    item_data['latest_human_version'] = f'{item_data["latest_app_version"]}_'
                item_data['latest_human_version'] += k

    if unhealthy_versions:
        item_data['healthy_error'] = f'Errors were found with {", ".join(unhealthy_versions)} version(s)'
    else:
        item_data['healthy'] = True
    if not retrieve_versions:
        item_data.pop('versions')

    return item_data


def get_item_details_impl(item_path: str, schema: str, questions_context: dict, options: dict) -> dict:
    # Each directory under item path represents a version of the item and we need to retrieve details
    # for each version available under the item
    retrieve_latest_version = options.get('retrieve_latest_version')
    item_data = {'versions': {}}
    with open(os.path.join(item_path, 'item.yaml'), 'r') as f:
        item_data.update(yaml.safe_load(f.read()))

    item_data.update({k: item_data.get(k) for k in ITEM_KEYS})

    for version in sorted(
        filter(lambda p: os.path.isdir(os.path.join(item_path, p)), os.listdir(item_path)),
        reverse=True, key=parse_version,
    ):
        item_data['versions'][version] = version_details = {
            'healthy': False,
            'supported': False,
            'healthy_error': None,
            'location': os.path.join(item_path, version),
            'required_features': [],
            'human_version': version,
            'version': version,
        }
        try:
            validate_item_version(version_details['location'], f'{schema}.{version}')
        except ValidationErrors as verrors:
            version_details['healthy_error'] = f'Following error(s) were found with {schema}.{version!r}:\n'
            for verror in verrors:
                version_details['healthy_error'] += f'{verror[0]}: {verror[1]}'

            # There is no point in trying to see what questions etc the version has as it's invalid
            continue

        version_details.update({
            'healthy': True,
            **get_item_version_details(version_details['location'], questions_context)
        })
        if retrieve_latest_version:
            break

    return item_data


def get_item_version_details(version_path: str, questions_context: dict) -> dict:
    version_data = {'location': version_path, 'required_features': set()}
    for key, filename, parser in (
        ('chart_metadata', 'Chart.yaml', yaml.safe_load),
        ('schema', 'questions.yaml', yaml.safe_load),
        ('app_readme', 'app-readme.md', markdown.markdown),
        ('detailed_readme', 'README.md', markdown.markdown),
        ('changelog', 'CHANGELOG.md', markdown.markdown),
    ):
        if os.path.exists(os.path.join(version_path, filename)):
            with open(os.path.join(version_path, filename), 'r') as f:
                version_data[key] = parser(f.read())
        else:
            version_data[key] = None

    # We will normalise questions now so that if they have any references, we render them accordingly
    # like a field referring to available interfaces on the system
    normalise_questions(version_data, questions_context)

    version_data.update({
        'supported': version_supported(version_data),
        'required_features': list(version_data['required_features']),
        'values': get_item_default_values(version_data)
    })
    chart_metadata = version_data['chart_metadata']
    if chart_metadata['name'] != 'ix-chart' and chart_metadata.get('appVersion'):
        version_data['human_version'] = f'{chart_metadata["appVersion"]}_{chart_metadata["version"]}'

    return version_data
