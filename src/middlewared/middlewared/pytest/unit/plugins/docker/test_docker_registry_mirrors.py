import logging
from unittest.mock import patch

import pytest
from pydantic import ValidationError as PydanticValidationError

from middlewared.api.current import DockerEntry, DockerUpdate
from middlewared.api.current import DockerRegistryMirror
from middlewared.service.context import ServiceContext
from middlewared.service_exception import ValidationErrors
from middlewared.plugins.docker.config import DockerConfigServicePart
from middlewared.pytest.unit.middleware import Middleware


def make_svc_part(m):
    context = ServiceContext(m, logging.getLogger('test'))
    return DockerConfigServicePart(context)


DEFAULTS = dict(id=1, enable_image_updates=True, nvidia=False, cidr_v6='fdd0::/64', address_pools=[])


@pytest.mark.parametrize('new_mirrors,old_mirrors,error_msgs', [
    (
        [
            DockerRegistryMirror(url='https://mirror1.example.com', insecure=False),
            DockerRegistryMirror(url='https://mirror2.example.com', insecure=False),
            DockerRegistryMirror(url='http://insecure1.example.com', insecure=True),
            DockerRegistryMirror(url='http://insecure2.example.com', insecure=True),
        ],
        [],
        []
    ),
    (
        [
            DockerRegistryMirror(url='https://mirror1.example.com', insecure=False),
            DockerRegistryMirror(url='https://mirror1.example.com', insecure=False),
        ],
        [],
        ['Duplicate registry mirror: https://mirror1.example.com/']
    ),
    (
        [
            DockerRegistryMirror(url='http://insecure1.example.com', insecure=True),
            DockerRegistryMirror(url='http://insecure1.example.com', insecure=True),
        ],
        [],
        ['Duplicate registry mirror: http://insecure1.example.com/']
    ),
])
@pytest.mark.asyncio
async def test_docker_registry_mirrors_validation(new_mirrors, old_mirrors, error_msgs):
    m = Middleware()
    m['interface.ip_in_use'] = lambda *arg: []
    m['system.is_ha_capable'] = lambda *arg: False
    svc_part = make_svc_part(m)

    new_config = DockerEntry.model_construct(
        **DEFAULTS, pool='tank', dataset='tank/ix-apps', registry_mirrors=new_mirrors,
    )
    old_config = DockerEntry.model_construct(
        **DEFAULTS, pool='tank', dataset='tank/ix-apps', registry_mirrors=old_mirrors,
    )

    with patch('middlewared.plugins.docker.config.query_imported_fast_impl') as run:
        run.return_value = {'5714764211007133142': {'name': 'tank', 'state': 'ONLINE'}}

        if not error_msgs:
            assert await svc_part.validate(old_config, new_config, False) is None
        else:
            with pytest.raises(ValidationErrors) as ve:
                await svc_part.validate(old_config, new_config, False)
            for i in range(len(error_msgs)):
                assert ve.value.errors[i].errmsg == error_msgs[i]


def test_http_mirror_without_insecure_rejected():
    """HTTP registry mirror URL without insecure=True is rejected by Pydantic model validation."""
    with pytest.raises(PydanticValidationError):
        DockerUpdate(registry_mirrors=[
            {'url': 'http://insecure1.example.com', 'insecure': False},
        ])
