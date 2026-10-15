import pytest

from middlewared.plugins.zettarepl.datasets import reverse_source_target_datasets


@pytest.mark.parametrize("source_datasets,target_dataset,reversed_source_datasets,reversed_target_dataset", [
    (["tank/work"], "backup/tank-work",
     ["backup/tank-work"], "tank/work"),
    (["tank/work/alice", "tank/work/bob"], "backup/tank-work",
     ["backup/tank-work/alice", "backup/tank-work/bob"], "tank/work"),
])
def test__reverse_source_target_datasets(source_datasets, target_dataset, reversed_source_datasets,
                                         reversed_target_dataset):
    assert reverse_source_target_datasets(source_datasets, target_dataset) == (
        reversed_source_datasets,
        reversed_target_dataset,
    )
