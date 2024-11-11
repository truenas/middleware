import os

from middlewared.utils.time_utils import utc_now


def get_dataset_recursive(datasets, directory):
    datasets = [
        dict(dataset, prefixlen=len(
            os.path.dirname(os.path.commonprefix(
                [dataset["properties"]["mountpoint"]["value"] + "/", directory + "/"]))
        ))
        for dataset in datasets
        if dataset["properties"]["mountpoint"]["value"] != "none"
    ]

    dataset = sorted(
        [
            dataset
            for dataset in datasets
            if (directory + "/").startswith(dataset["properties"]["mountpoint"]["value"] + "/")
        ],
        key=lambda dataset: dataset["prefixlen"],
        reverse=True
    )[0]

    return dataset, any(
        (ds["properties"]["mountpoint"]["value"] + "/").startswith(directory + "/")
        for ds in datasets
        if ds != dataset
    )


async def create_snapshot(middleware, path, name="cloud_task-onetime") -> tuple[str, str]:
    """Create a ZFS snapshot given a dataset path; return its name and path."""
    dataset, recursive = get_dataset_recursive(
        await middleware.call("zfs.dataset.query", [["type", "=", "FILESYSTEM"]]),
        path,
    )
    snapshot_name = f"{name}-{utc_now().strftime('%Y%m%d%H%M%S')}"

    snapshot = (await middleware.call("zfs.snapshot.create", {
        "dataset": dataset["name"],
        "name": snapshot_name,
        "recursive": recursive
    }))["name"]

    mountpoint = dataset["properties"]["mountpoint"]["value"]
    path = os.path.normpath(os.path.join(
        mountpoint, ".zfs", "snapshot", snapshot_name, os.path.relpath(path, mountpoint)
    ))

    return snapshot, path
