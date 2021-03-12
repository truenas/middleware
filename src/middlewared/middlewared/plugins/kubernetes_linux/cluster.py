from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import Service

from .k8s import api_client
from .k8s.cluster import create_from_yaml
from .k8s.exceptions import FailToCreateError


class KubernetesClusterService(Service):

    class Config:
        namespace = 'k8s.cluster'
        private = True

    @accepts(
        Str('file_path'),
        Dict(
            'options',
            Bool('suppress_already_created_exception', default=True)
        )
    )
    async def apply_yaml_file(self, file_path, options):
        async with api_client() as (api, context):
            try:
                await create_from_yaml(api, file_path)
            except FailToCreateError:
                if not options['suppress_already_created_exception']:
                    raise
