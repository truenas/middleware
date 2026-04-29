import contextlib
import os
import shutil
import stat

import truenas_os

from middlewared.utils.filesystem.copy import (
    CopyTreeConfig,
    clone_or_copy_file,
    copytree,
)


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


def _copy_nvram_file(src: str, dst: str) -> None:
    """Symlink-safe single-file copy with O_EXCL no-clobber.

    Uses clone_or_copy_file for the byte transfer (block clone on ZFS,
    sendfile/userspace fallback). Replicates source uid/gid, mode, and
    atime/mtime via fd-based syscalls. xattrs are NOT copied — NVRAM
    files written by libvirt/OVMF do not carry meaningful xattrs.

    Symlink protection is O_NOFOLLOW on both endpoints; O_EXCL on dst
    refuses to clobber any pre-existing inode. If anything fails after
    dst was created, the partial dst is unlinked before re-raising.

    Raises:
        FileNotFoundError: src does not exist.
        FileExistsError: dst already exists (file/symlink/dir).
        OSError: on symlink at src/dst (ELOOP), I/O failure, etc.
    """
    src_fd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        src_st = os.fstat(src_fd)
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        dst_fd = os.open(dst, flags, mode=0o600)
        try:
            try:
                clone_or_copy_file(src_fd, dst_fd)
                os.fchown(dst_fd, src_st.st_uid, src_st.st_gid)
                os.fchmod(dst_fd, stat.S_IMODE(src_st.st_mode))
                os.utime(dst_fd, ns=(src_st.st_atime_ns, src_st.st_mtime_ns))
            except Exception:
                # dst was created by O_CREAT|O_EXCL above; remove the
                # partial file before propagating so callers don't see
                # half-written state.
                with contextlib.suppress(OSError):
                    os.unlink(dst)
                raise
        finally:
            os.close(dst_fd)
    finally:
        os.close(src_fd)


def copy_vm_state(src_id: int, src_name: str, dst_id: int, dst_name: str) -> None:
    """Copy NVRAM file and TPM state dir from one VM slot to another.

    Used by clone — the destination slot must not already exist (the
    clone just allocated a fresh DB id, so any pre-existing file/dir
    is stale state from a deleted VM and we abort rather than clobber
    it).

    Missing sources are silently skipped — a never-booted source has
    no on-disk state and libvirt/swtpm will initialise fresh state
    when the clone first boots.

    Cleanup discipline:
        FileNotFoundError (src missing) -> silent skip; for TPM,
            os.rmdir the empty dst dir copytree creates before
            discovering src is gone.
        FileExistsError  (dst pre-existed) -> propagate; we never
            created dst, so do NOT touch it.
        any other exception (mid-copy)    -> we created dst, clean up
            the partial file/tree before re-raising.
    """
    src_nvram = vm_nvram_path(src_id, src_name)
    dst_nvram = vm_nvram_path(dst_id, dst_name)
    src_tpm = vm_tpm_path(src_id, src_name)
    dst_tpm = vm_tpm_path(dst_id, dst_name)

    nvram_copied = False
    try:
        try:
            _copy_nvram_file(src_nvram, dst_nvram)
            nvram_copied = True
        except FileNotFoundError:
            pass

        try:
            copytree(src_tpm, dst_tpm, CopyTreeConfig(exist_ok=False))
        except FileNotFoundError:
            # copytree calls os.mkdir(dst) before iterating src, so a
            # missing src leaves an empty dst behind. Remove it.
            with contextlib.suppress(OSError):
                os.rmdir(dst_tpm)
            return
        except FileExistsError:
            # dst_tpm pre-existed; we never wrote to it. Do NOT rmtree.
            raise
        except Exception:
            with contextlib.suppress(OSError):
                shutil.rmtree(dst_tpm)
            raise
    except Exception:
        if nvram_copied:
            with contextlib.suppress(OSError):
                os.unlink(dst_nvram)
        raise


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
