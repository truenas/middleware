import os

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.pool_.utils import CreateImplArgs
from middlewared.service import CallError, ServiceContext
from middlewared.utils.filesystem.perms import enforce_dir_perms

from .utils import CONTAINER_DS_NAME, container_dataset, container_dataset_mountpoint

CONTAINER_DS_PARENT_DIR = f"/mnt/{CONTAINER_DS_NAME}"


async def ensure_datasets(context: ServiceContext, pool: str) -> None:
    main_dataset = container_dataset(pool)
    main_dataset_mountpoint = container_dataset_mountpoint(pool)

    datasets = [f"{main_dataset}/containers", f"{main_dataset}/images"]

    existing_datasets = set()
    for dataset in await context.call2(
        context.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[main_dataset] + datasets, properties=["mountpoint"])
    ):
        if dataset["type"] != "FILESYSTEM":
            raise CallError(f"Expected dataset {dataset['name']!r} to be FILESYSTEM, but it is {dataset['type']}")

        if dataset["name"] == main_dataset:
            main_dataset_mountpoint_value = f"/mnt{main_dataset_mountpoint}"
            if dataset["properties"]["mountpoint"]["value"] != main_dataset_mountpoint_value:
                raise CallError(
                    f"Expected dataset {dataset['name']} to have mountpoint of {main_dataset_mountpoint_value!r}, "
                    f"but it is {dataset['properties']['mountpoint']['value']!r}."
                )

        existing_datasets.add(dataset["name"])

    if main_dataset not in existing_datasets:
        await context.middleware.call(
            "pool.dataset.create_impl",
            CreateImplArgs(
                name=main_dataset,
                ztype="FILESYSTEM",
                zprops={
                    "mountpoint": main_dataset_mountpoint,
                    "acltype": "posix",
                    "aclmode": "discard",
                    "snapdir": "hidden",
                },
            ),
        )

    if not await context.to_thread(os.path.ismount, f"/mnt{main_dataset_mountpoint}"):
        await context.call2(context.s.zfs.resource.mount, main_dataset)

    for ds_name in datasets:
        if ds_name not in existing_datasets:
            await context.middleware.call("pool.dataset.create_impl", CreateImplArgs(name=ds_name, ztype="FILESYSTEM"))
        await context.call2(context.s.zfs.resource.mount, ds_name)

    # ZFS auto-creates CONTAINER_DS_PARENT_DIR as a side effect of mounting the
    # per-pool dataset. Restrict it so non-root host users can't traverse to
    # any container's on-disk rootfs (UID-collision exposure for apps user etc.).
    await context.to_thread(enforce_dir_perms, CONTAINER_DS_PARENT_DIR)
