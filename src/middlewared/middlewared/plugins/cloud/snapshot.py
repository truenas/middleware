import os

from middlewared.utils.time_utils import utc_now


async def create_snapshot(
    middleware, path, name="cloud_task-onetime"
) -> tuple[str, str]:
    """Create a ZFS snapshot for the dataset containing the specified path.

    This function creates a ZFS snapshot of the dataset that contains the given filesystem
    path. It uses filesystem.statfs to determine the dataset information, avoiding the need
    to traverse the dataset hierarchy or match dataset names to path components.

    The function intelligently determines whether a recursive snapshot is needed based on
    whether the target path is at the dataset's mountpoint or within a subdirectory.

    Args:
        middleware: TrueNAS middleware instance for making API calls
        path (str): Absolute filesystem path to snapshot. This can be either:
            - A dataset mountpoint (e.g., "/mnt/tank/dataset")
            - A subdirectory within a dataset (e.g., "/mnt/tank/dataset/folder/subfolder")
        name (str, optional): Prefix for the snapshot name. Defaults to "cloud_task-onetime".
            The final snapshot name will be "{name}-{timestamp}" where timestamp is
            formatted as YYYYMMDDHHMMSS in UTC.

    Returns:
        tuple[str, str]: A tuple containing:
            - snapshot_name (str): The full ZFS snapshot name in format "dataset@snapshot_name"
            - snapshot_path (str): The filesystem path to access the snapshot contents
              at the originally requested path via .zfs/snapshot

    Behavior:
        1. Calls filesystem.statfs on the target path to get dataset information
        2. Determines if recursive snapshot is needed:
           - recursive=True when path equals the dataset mountpoint (st["dest"])
             This ensures child datasets are included when snapshotting at dataset root
           - recursive=False when path is a subdirectory within the dataset
             Child datasets cannot be mounted under arbitrary subdirectories
        3. Creates the snapshot with a timestamped name
        4. Constructs the snapshot access path using the .zfs/snapshot snapdir,
           preserving the full path to the originally requested directory

    Examples:
        # Snapshot at dataset mountpoint (recursive=True)
        path = "/mnt/tank/users"  # mountpoint of tank/users dataset
        # statfs returns: {"source": "tank/users", "dest": "/mnt/tank/users", ...}
        # Creates: tank/users@cloud_task-onetime-20240115120530 (recursive)
        # Returns:
        #   (
        #       "tank/users@cloud_task-onetime-20240115120530",
        #       "/mnt/tank/users/.zfs/snapshot/cloud_task-onetime-20240115120530"
        #   )

        # Snapshot of subdirectory (recursive=False)
        path = "/mnt/tank/users/alice/documents"  # subdirectory in tank/users dataset
        # statfs returns: {"source": "tank/users", "dest": "/mnt/tank/users", ...}
        # Creates: tank/users@cloud_task-onetime-20240115120530 (non-recursive)
        # Returns:
        #   (
        #       "tank/users@cloud_task-onetime-20240115120530",
        #       "/mnt/tank/users/.zfs/snapshot/cloud_task-onetime-20240115120530/alice/documents"
        #   )
    """
    st = await middleware.call("filesystem.statfs", path)
    snapshot_name = f"{name}-{utc_now().strftime('%Y%m%d%H%M%S')}"
    snapshot = await middleware.call(
        "zfs.resource.snapshot.create_impl",
        {
            "dataset": st["source"],
            "name": snapshot_name,
            "recursive": st["dest"] == path,
        },
    )
    # Construct the full path to the snapshot, including any subdirectory
    snapshot_path = os.path.join(
        st["dest"],
        ".zfs",
        "snapshot",
        snapshot_name,
        os.path.relpath(path, st["dest"]) if path != st["dest"] else "",
    )
    return snapshot["name"], os.path.normpath(snapshot_path)
