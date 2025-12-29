import enum
from typing import Any

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


def safe_yaml_load(stream) -> Any:
    """
    Helper function to safely load YAML data using CSafeLoader.

    CSafeLoader is functionally identical to SafeLoader but uses a C implementation
    which is significantly faster and releases the GIL during parsing. This is
    particularly important in multi-threaded environments where python-native YAML
    parsing can cause GIL contention and starve the asyncio event loop.

    Args:
        stream: A string or file-like object containing YAML data

    Returns:
        The parsed YAML data structure (dict, list, str, etc.)
    """
    return yaml.load(stream, Loader=yaml.CSafeLoader)


def dump_yaml(data, **kwargs):
    """
    Helper function to dump YAML with proper string quoting.

    This ensures all strings are quoted to prevent unintended type conversions
    (e.g., '8E1' becoming 80.0, 'true' becoming boolean True, etc.)

    Args:
        data: The data structure to serialize to YAML
        **kwargs: Additional arguments to pass to yaml.dump()
                  (e.g., default_flow_style, sort_keys, etc.)

    Returns:
        The YAML string representation of the data
    """
    kwargs['Dumper'] = QuotedStrDumper
    return yaml.dump(data, **kwargs)


def get_app_name_from_project_name(project_name: str) -> str:
    return project_name[len(PROJECT_PREFIX):]
