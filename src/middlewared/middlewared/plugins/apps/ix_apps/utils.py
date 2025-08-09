import enum

import yaml

from catalog_reader.library import RE_VERSION  # noqa
from middlewared.plugins.apps_images.utils import normalize_reference  # noqa
from middlewared.plugins.apps.schema_construction_utils import CONTEXT_KEY_NAME  # noqa
from middlewared.plugins.apps.utils import IX_APPS_MOUNT_PATH, PROJECT_PREFIX, run  # noqa


class AppState(enum.Enum):
    CRASHED = 'CRASHED'
    DEPLOYING = 'DEPLOYING'
    RUNNING = 'RUNNING'
    STOPPED = 'STOPPED'
    STOPPING = 'STOPPING'


class ContainerState(enum.Enum):
    CRASHED = 'crashed'
    CREATED = 'created'
    EXITED = 'exited'
    RUNNING = 'running'
    STARTING = 'starting'


class QuotedStrDumper(yaml.SafeDumper):
    pass


def _repr_str(dumper, data: str):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')


QuotedStrDumper.add_representer(str, _repr_str)


def get_app_name_from_project_name(project_name: str) -> str:
    return project_name[len(PROJECT_PREFIX):]
