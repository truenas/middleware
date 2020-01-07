from types import SimpleNamespace

from zettarepl.replication.task.dataset import get_source_dataset_base, get_target_dataset

from middlewared.service import Service


class ZettareplService(Service):

    class Config:
        private = True

    async def reverse_source_target_datasets(self, source_datasets, target_dataset):
        if len(source_datasets) == 1:
            return [target_dataset], source_datasets[0]
        else:
            replication_task = SimpleNamespace(source_datasets=source_datasets, target_dataset=target_dataset)
            return (
                [
                    get_target_dataset(replication_task, source_dataset)
                    for source_dataset in source_datasets
                ],
                get_source_dataset_base(replication_task)
            )
