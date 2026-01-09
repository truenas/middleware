import os
import truenas_os


def create_mount_one(dataset_spec: dict) -> int:
    """
    Assemble a new detached mount object based on the provided spec
    and return an open file descriptor for it
    """
    fsfd = truenas_os.fsopen(fs_name='zfs', flags=truenas_os.FSOPEN_CLOEXEC)
    truenas_os.fsconfig(
        fs_fd=fsfd,
        cmd=truenas_os.FSCONFIG_SET_STRING,
        key='source',
        value=dataset_spec['name']
    )
    truenas_os.fsconfig(fs_fd=fsfd, cmd=truenas_os.FSCONFIG_CMD_CREATE)
    mntfd = truenas_os.fsmount(fs_fd=fsfd, flags=truenas_os.FSMOUNT_CLOEXEC)
    os.close(fsfd)
    return mntfd


def create_mount_tree(*, datasets: list) -> int:
    """
    Assemble a mount tree based on the provided specification and return an
    open file descriptor referencing a detatched mount object. This file
    descriptor can then be used with truenas_os.move_mount to actually mount
    at a given path.
    """
    root = None

    for ds in datasets:
        mntfd = create_mount_one(ds)
        if root is None:
            root = mntfd
        else:
            truenas_os.move_mount(
                from_dirfd=mntfd,
                from_path="",
                to_dirfd=root,
                to_path=os.path.basename(ds['name']),
                flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH
            )
            os.close(mntfd)

    return root


def mount_hierarchy(*, target_fd: int, datasets: list) -> None:
    """ Mount the specified dataset hierarchy to the given path represented by target_fd """
    mnt_fd = create_mount_tree(datasets=datasets)
    truenas_os.move_mount(
        from_dirfd=mnt_fd,
        from_path="",
        to_dirfd=target_fd,
        to_path="",
        flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH|truenas_os.MOVE_MOUNT_T_EMPTY_PATH
    )
    os.close(mnt_fd)
