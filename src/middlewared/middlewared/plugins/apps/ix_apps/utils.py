from catalog_reader.library import RE_VERSION  # noqa
from middlewared.plugins.apps.schema_utils import CONTEXT_KEY_NAME  # noqa
from middlewared.plugins.apps.utils import IX_APPS_MOUNT_PATH, PROJECT_PREFIX, run  # noqa


def get_app_name_from_project_name(project_name: str) -> str:
    return project_name[len(PROJECT_PREFIX):]
