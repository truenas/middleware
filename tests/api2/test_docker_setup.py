import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.docker import dataset_props


@pytest.fixture(scope='module')
def docker_pool():
    with another_pool() as pool:
        yield pool['name']


@pytest.mark.dependency(name='docker_setup')
def test_docker_setup(docker_pool):
    docker_config = call('docker.update', {'pool': docker_pool}, job=True)
    assert docker_config['pool'] == docker_pool, docker_config


@pytest.mark.dependency(depends=['docker_setup'])
def test_docker_datasets_properties():
    docker_config = call('docker.config')
    datasets = {
        ds['name']: ds['properties'] for ds in call('zfs.dataset.query', [['id', '^', docker_config['dataset']]])
    }
    for ds_name, current_props in datasets.items():
        invalid_props = {}
        for to_check_prop, to_check_prop_value in dataset_props(ds_name).items():
            if current_props[to_check_prop]['value'] != to_check_prop_value:
                invalid_props[to_check_prop] = current_props[to_check_prop]['value']

        assert invalid_props == {}, f'{ds_name} has invalid properties: {invalid_props}'


def test_unset_docker_pool(docker_pool):
    docker_config = call('docker.update', {'pool': None}, job=True)
    assert docker_config['pool'] is None, docker_config
