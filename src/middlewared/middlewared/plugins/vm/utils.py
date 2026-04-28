import contextlib
import os
import shutil

import truenas_os

SYSTEM_TPM_FOLDER_PATH = '/var/db/system/vm/tpm'
SYSTEM_NVRAM_FOLDER_PATH = '/var/db/system/vm/nvram'
LIBVIRT_QEMU_UID = 986
LIBVIRT_QEMU_GID = 986


def get_vm_tpm_state_dir_name(id_: int, name: str) -> str:
    return f'{id_}_{name}_tpm_state'


def get_vm_nvram_file_name(id_: int, name: str) -> str:
    return f'{id_}_{name}_VARS.fd'


def vm_nvram_path(id_: int, name: str) -> str:
    return os.path.join(SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name(id_, name))


def vm_tpm_path(id_: int, name: str) -> str:
    return os.path.join(SYSTEM_TPM_FOLDER_PATH, get_vm_tpm_state_dir_name(id_, name))


def _open_state_parent(path: str) -> int:
    # RESOLVE_NO_SYMLINKS guards against an attacker dropping a symlink inside
    # /var/db/system/vm/{nvram,tpm} between our checks and the actual rename.
    # O_PATH is enough: the fd is only used as an anchor for *at() syscalls.
    assert path in (SYSTEM_NVRAM_FOLDER_PATH, SYSTEM_TPM_FOLDER_PATH), path
    return truenas_os.openat2(
        path,
        os.O_PATH | os.O_DIRECTORY,
        resolve=truenas_os.RESOLVE_NO_SYMLINKS,
    )


def rename_vm_state(old_id: int, old_name: str, new_id: int, new_name: str) -> None:
    """Rename NVRAM file and TPM state directory for a VM.

    renameat2 is atomic on the same filesystem and preserves the inode, so
    ownership/mode/xattrs survive the rename (NVRAM stays libvirt-qemu, the
    per-VM TPM dir stays tss-owned with its .lock and tpm2-00.permall).

    Missing sources are silently skipped — a VM that has never booted has no
    on-disk state and libvirt/swtpm will initialise both on first start.

    AT_RENAME_NOREPLACE ensures we fail loudly if the destination already
    exists (e.g. stale state from a previously deleted VM).

    All-or-nothing: if NVRAM renames but TPM then raises, the NVRAM rename
    is reverted before the original exception propagates.
    """
    nvram_fd = _open_state_parent(SYSTEM_NVRAM_FOLDER_PATH)
    try:
        tpm_fd = _open_state_parent(SYSTEM_TPM_FOLDER_PATH)
        try:
            items = [
                (
                    nvram_fd,
                    get_vm_nvram_file_name(old_id, old_name),
                    get_vm_nvram_file_name(new_id, new_name),
                ),
                (
                    tpm_fd,
                    get_vm_tpm_state_dir_name(old_id, old_name),
                    get_vm_tpm_state_dir_name(new_id, new_name),
                ),
            ]
            performed: list[tuple[int, str, str]] = []
            try:
                for parent_fd, src, dst in items:
                    try:
                        truenas_os.renameat2(
                            src,
                            dst,
                            src_dir_fd=parent_fd,
                            dst_dir_fd=parent_fd,
                            flags=truenas_os.AT_RENAME_NOREPLACE,
                        )
                    except FileNotFoundError:
                        continue
                    performed.append((parent_fd, src, dst))
            except Exception:
                for parent_fd, src, dst in reversed(performed):
                    with contextlib.suppress(OSError):
                        truenas_os.renameat2(
                            dst,
                            src,
                            src_dir_fd=parent_fd,
                            dst_dir_fd=parent_fd,
                            flags=truenas_os.AT_RENAME_NOREPLACE,
                        )
                raise
        finally:
            os.close(tpm_fd)
    finally:
        os.close(nvram_fd)


def delete_vm_state(id_: int, name: str) -> None:
    """Remove NVRAM file and TPM state dir for a VM. Best-effort and idempotent."""
    nvram_fd = _open_state_parent(SYSTEM_NVRAM_FOLDER_PATH)
    try:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(get_vm_nvram_file_name(id_, name), dir_fd=nvram_fd)
    finally:
        os.close(nvram_fd)

    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(vm_tpm_path(id_, name))


def vm_state_missing_sources(
    id_: int, name: str, bootloader: str, tpm: bool
) -> list[str]:
    """Return which on-disk artefacts were expected but not present.

    Used after a successful rename to log a warning for never-booted VMs so
    operators know libvirt/swtpm will initialise fresh state on next start.
    """
    missing: list[str] = []
    if bootloader == 'UEFI' and not os.path.exists(vm_nvram_path(id_, name)):
        missing.append('NVRAM')
    if tpm and not os.path.exists(vm_tpm_path(id_, name)):
        missing.append('TPM')
    return missing
