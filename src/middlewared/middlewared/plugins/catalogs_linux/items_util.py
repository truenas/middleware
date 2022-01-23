import markdown
import os
import yaml

from middlewared.plugins.chart_releases_linux.schema import construct_schema

from .features import version_supported
from .questions_utils import normalise_questions


def get_item_default_values(version_details: dict) -> dict:
    return construct_schema(version_details, {}, False)['new_values']


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
