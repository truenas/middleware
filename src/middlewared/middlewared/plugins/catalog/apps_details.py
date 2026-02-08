import contextlib
import json
import os

from apps_ci.names import CACHED_CATALOG_FILE_NAME
from jsonschema import validate as json_schema_validate, ValidationError as JsonValidationError

from middlewared.api import api_method
from middlewared.api.current import CatalogAppsArgs, CatalogAppsResult
from middlewared.service import private, Service

from .apps_details_new import get_normalized_questions_context, retrieve_recommended_apps
from .apps_util import get_app_version_details
from .utils import get_cache_key, OFFICIAL_LABEL


class CatalogService(Service):

    class Config:
        cli_namespace = 'app.catalog'

    @private
    def train_to_apps_version_mapping(self):
        mapping = {}
        for train, train_data in self.apps({
            'cache': True,
            'cache_only': True,
        }).items():
            mapping[train] = {}
            for app_data in train_data.values():
                mapping[train][app_data['name']] = {
                    'version': app_data['latest_version'],
                    'app_version': app_data['latest_app_version'],
                }

        return mapping
