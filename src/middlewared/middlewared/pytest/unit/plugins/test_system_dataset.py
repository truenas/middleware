import jsonschema
import pytest

from middlewared.plugins.system_dataset.hierarchy import get_system_dataset_spec, SYSTEM_DATASET_JSON_SCHEMA


@pytest.mark.parametrize('pool_name,uuid', [
    ('test', '12345678'),
    ('test2', '12345679'),
])
@pytest.mark.asyncio
async def test_system_dataset_spec(pool_name, uuid):
    jsonschema.validate(get_system_dataset_spec(pool_name, uuid), SYSTEM_DATASET_JSON_SCHEMA)
