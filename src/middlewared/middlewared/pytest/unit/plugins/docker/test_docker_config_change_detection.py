import logging

import pytest

from middlewared.api.current import DockerAddressPool, DockerEntry, DockerRegistryMirror, DockerUpdate
from middlewared.plugins.docker.config import DockerConfigServicePart
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service.context import ServiceContext


def make_svc_part(m):
    context = ServiceContext(m, logging.getLogger('test'))
    return DockerConfigServicePart(context)


DB_DEFAULTS = dict(
    id=1, enable_image_updates=True, pool='tank', cidr_v6='fdd0::/64',
    address_pools=[
        {'base': '172.17.0.0/12', 'size': 24},
        {'base': 'fdd0::/48', 'size': 64},
    ],
    registry_mirrors=[],
)


@pytest.mark.asyncio
async def test_extend_constructs_typed_address_pools():
    m = Middleware()
    m['system.advanced.config'] = lambda *a: {'nvidia': False}
    svc = make_svc_part(m)

    data = dict(DB_DEFAULTS)
    result = await svc.extend(data)
    assert all(isinstance(p, DockerAddressPool) for p in result['address_pools'])


@pytest.mark.asyncio
async def test_extend_constructs_typed_registry_mirrors():
    m = Middleware()
    m['system.advanced.config'] = lambda *a: {'nvidia': False}
    svc = make_svc_part(m)

    data = dict(DB_DEFAULTS, registry_mirrors=[
        {'url': 'https://mirror.example.com', 'insecure': False},
    ])
    result = await svc.extend(data)
    assert all(isinstance(r, DockerRegistryMirror) for r in result['registry_mirrors'])


@pytest.mark.asyncio
async def test_address_pools_equal_after_updated_with_same_values():
    """old_config (from extend+model_construct) and new_config (from updated with DockerUpdate) compare equal."""
    m = Middleware()
    m['system.advanced.config'] = lambda *a: {'nvidia': False}
    svc = make_svc_part(m)

    data = dict(DB_DEFAULTS)
    extended = await svc.extend(data)
    old_config = DockerEntry.model_construct(**extended)

    # Simulate user sending same address_pools values via DockerUpdate
    update = DockerUpdate(address_pools=[
        {'base': '172.17.0.0/12', 'size': 24},
        {'base': 'fdd0::/48', 'size': 64},
    ])
    new_config = old_config.updated(update)
    assert new_config.address_pools == old_config.address_pools


@pytest.mark.asyncio
async def test_address_pools_not_equal_after_updated_with_different_values():
    m = Middleware()
    m['system.advanced.config'] = lambda *a: {'nvidia': False}
    svc = make_svc_part(m)

    data = dict(DB_DEFAULTS)
    extended = await svc.extend(data)
    old_config = DockerEntry.model_construct(**extended)

    update = DockerUpdate(address_pools=[
        {'base': '10.0.0.0/8', 'size': 24},
    ])
    new_config = old_config.updated(update)
    assert new_config.address_pools != old_config.address_pools


@pytest.mark.asyncio
async def test_registry_mirrors_equal_after_updated_with_same_values():
    m = Middleware()
    m['system.advanced.config'] = lambda *a: {'nvidia': False}
    svc = make_svc_part(m)

    mirrors = [{'url': 'https://mirror.example.com', 'insecure': False}]
    data = dict(DB_DEFAULTS, registry_mirrors=mirrors)
    extended = await svc.extend(data)
    old_config = DockerEntry.model_construct(**extended)

    update = DockerUpdate(registry_mirrors=mirrors)
    new_config = old_config.updated(update)
    assert new_config.registry_mirrors == old_config.registry_mirrors


@pytest.mark.asyncio
async def test_registry_mirrors_not_equal_after_updated_with_different_values():
    m = Middleware()
    m['system.advanced.config'] = lambda *a: {'nvidia': False}
    svc = make_svc_part(m)

    data = dict(DB_DEFAULTS, registry_mirrors=[
        {'url': 'https://mirror1.example.com', 'insecure': False},
    ])
    extended = await svc.extend(data)
    old_config = DockerEntry.model_construct(**extended)

    update = DockerUpdate(registry_mirrors=[
        {'url': 'https://mirror2.example.com', 'insecure': False},
    ])
    new_config = old_config.updated(update)
    assert new_config.registry_mirrors != old_config.registry_mirrors


def test_cidr_v6_str_comparison_same_values():
    """str() wrapping makes same-value cidr_v6 comparison work across str and IPvAnyInterface types."""
    old_config = DockerEntry.model_construct(cidr_v6='fdd0::/64')
    update = DockerUpdate(cidr_v6='fdd0::/64')
    new_config = old_config.updated(update)
    assert str(new_config.cidr_v6) == str(old_config.cidr_v6)


def test_cidr_v6_str_comparison_different_values():
    """str() wrapping still detects different cidr_v6 values."""
    old_config = DockerEntry.model_construct(cidr_v6='fdd0::/64')
    update = DockerUpdate(cidr_v6='fdd1::/64')
    new_config = old_config.updated(update)
    assert str(new_config.cidr_v6) != str(old_config.cidr_v6)
