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


def mount_hierarchy(*, target_fd: int, datasets: list) -> None:
    """ Mount the specified dataset hierarchy to the given path represented by target_fd """
    for idx, ds in enumerate(datasets):
        mntfd = create_mount_one(ds)
        if idx == 0:
            truenas_os.move_mount(
                from_dirfd=mntfd,
                from_path="",
                to_dirfd=target_fd,
                to_path="",
                flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH|truenas_os.MOVE_MOUNT_T_EMPTY_PATH
            )
        else:
            target_path = os.path.basename(ds['name'])
            chown_config = ds['chown_config']
            mode_perms = chown_config.pop('mode')

            try:
                os.mkdir(target_path, dir_fd=target_fd, mode=mode_perms)
            except FileExistsError:
                os.chmod(target_path, dir_fd=target_fd, mode=mode_perms)

            os.chown(target_path, dir_fd=target_fd, **chown_config)

            truenas_os.move_mount(
                from_dirfd=mntfd,
                from_path="",
                to_dirfd=target_fd,
                to_path=target_path,
                flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH
            )

        os.close(mntfd)
