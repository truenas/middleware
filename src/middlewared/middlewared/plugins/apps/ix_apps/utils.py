import enum
from typing import Any, Literal, TypeAlias

import yaml

PROJECT_PREFIX = 'ix-'

# Kept in sync by hand with `AppEntry.error_reason` in middlewared.api.<current version>.app,
# which cannot import this module (API schemas may not import plugins).
AppErrorReason: TypeAlias = Literal['METADATA_MISSING', 'METADATA_UNREADABLE', 'METADATA_INCOMPLETE']


class AppState(enum.Enum):
    CRASHED = 'CRASHED'
    DEPLOYING = 'DEPLOYING'
    ERROR = 'ERROR'
    RUNNING = 'RUNNING'
    STOPPED = 'STOPPED'
    STOPPING = 'STOPPING'


# States in which an app's on-disk data is unusable, so it can only be deleted
UNUSABLE_STATES: frozenset[str] = frozenset({AppState.ERROR.value})


class ContainerState(enum.Enum):
    CRASHED = 'crashed'
    CREATED = 'created'
    EXITED = 'exited'
    RUNNING = 'running'
    STARTING = 'starting'


class QuotedStrDumper(yaml.SafeDumper):
    pass


def _repr_str(dumper: QuotedStrDumper, data: str) -> yaml.ScalarNode:
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')


QuotedStrDumper.add_representer(str, _repr_str)


def dump_yaml(data: Any, **kwargs: Any) -> str:
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
    return yaml.dump(data, **kwargs)  # type: ignore[no-any-return]


def get_app_name_from_project_name(project_name: str) -> str:
    return project_name[len(PROJECT_PREFIX):]
