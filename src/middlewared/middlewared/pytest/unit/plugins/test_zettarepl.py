import pytest

import middlewared.plugins.zettarepl  # noqa
import middlewared.plugins.zettarepl_.util  # noqa

from middlewared.pytest.unit.helpers import load_compound_service

ZettareplService = load_compound_service("zettarepl")


@pytest.mark.parametrize("source_datasets,target_dataset,reversed_source_datasets,reversed_target_dataset", [
    (["tank/work"], "backup/tank-work",
     ["backup/tank-work"], "tank/work"),
    (["tank/work/alice", "tank/work/bob"], "backup/tank-work",
     ["backup/tank-work/alice", "backup/tank-work/bob"], "tank/work"),
])
@pytest.mark.asyncio
async def test__reverse_source_target_datasets(source_datasets, target_dataset, reversed_source_datasets,
                                               reversed_target_dataset):
    zs = ZettareplService(None)
    assert await zs.reverse_source_target_datasets(source_datasets, target_dataset) == (
        reversed_source_datasets,
        reversed_target_dataset,
    )
