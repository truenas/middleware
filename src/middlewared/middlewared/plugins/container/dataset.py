import os

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.pool_.utils import CreateImplArgs
from middlewared.service import CallError, ServiceContext

from .utils import container_dataset, container_dataset_mountpoint


async def ensure_datasets(context: ServiceContext, pool: str) -> None:
    main_dataset = container_dataset(pool)
    main_dataset_mountpoint = container_dataset_mountpoint(pool)

    datasets = [f"{main_dataset}/containers", f"{main_dataset}/images"]

    existing_datasets = set()
    for dataset in await context.call2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[main_dataset] + datasets, properties=["mountpoint"])
    ):
        if dataset["type"] != "FILESYSTEM":
            raise CallError(f'Expected dataset {dataset["name"]!r} to be FILESYSTEM, but it is {dataset["type"]}')

        if dataset["name"] == main_dataset:
            main_dataset_mountpoint_value = f"/mnt{main_dataset_mountpoint}"
            if dataset["properties"]["mountpoint"]["value"] != main_dataset_mountpoint_value:
                raise CallError(
                    f'Expected dataset {dataset["name"]} to have mountpoint of {main_dataset_mountpoint_value!r}, '
                    f'but it is {dataset["properties"]["mountpoint"]["value"]!r}.'
                )

        existing_datasets.add(dataset["name"])

    if main_dataset not in existing_datasets:
        await context.middleware.call(
            "pool.dataset.create_impl",
            CreateImplArgs(
                name=main_dataset, ztype="FILESYSTEM", zprops={"mountpoint": main_dataset_mountpoint},
            )
        )

    if not await context.to_thread(os.path.exists, main_dataset_mountpoint):
        await context.call2(context.s.zfs.resource.mount, main_dataset)

    for ds_name in datasets:
        if ds_name not in existing_datasets:
            await context.middleware.call(
                "pool.dataset.create_impl",
                CreateImplArgs(name=ds_name, ztype="FILESYSTEM")
            )
        await context.call2(context.s.zfs.resource.mount, ds_name)
