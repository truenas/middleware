#!/usr/bin/env python3

# WARNING: TrueNAS installs each version into its own boot environment (BE). This script
# regenerates the initramfs for a *target* BE whose rootfs path is passed as the `chroot`
# argument. The target BE is not necessarily the same as the environment executing this
# script: it can be invoked from
#   - a fresh-install ISO (host = installer environment, target = newly-extracted BE),
#   - an upgrade running on an existing TrueNAS (host = old/currently-running BE, target
#     = newly-extracted new BE), or
#   - the running system itself for a runtime regen (host = target, `chroot` = "/").
#
# In the first two cases this script is shipped inside the squashfs of the target BE (it
# gets unsquashed into the target rootfs before being invoked), but it is executed by the
# host's python interpreter without a wrapping `chroot`. The lazy imports below reference
# modules that may only exist in the target BE (or whose APIs differ from the host's), so
# we cannot rely on the host's `sys.path` to resolve them: we prepend the target BE's
# python dist-packages directory to `sys.path` (and `chroot` into the target BE for the
# `update-initramfs` invocation) so that those imports and that subprocess resolve
# against the target BE's modules rather than the host's. When `chroot == "/"` the host
# and target are the same BE, so this `sys.path` adjustment is skipped.
#
# For this reason we must keep imports at the head of this file to an absolute minimum
# (base cpython modules only, which are guaranteed to behave the same across BEs and
# installer environments) and lazy-import anything else down below where the
# "# BEGIN LAZY IMPORTS" comment is located, after `sys.path` has been adjusted to point
# at the target BE.
import argparse
import contextlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import textwrap

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def atomic_write_fallback(target, mode="w", *, tmppath=None, uid=0, gid=0, perms=0o644):
    # Stdlib-only stand-in for `truenas_os_pyutils.io.atomic_write`. The upstream version
    # transitively imports the `truenas_os` C extension; on an upgrade this script runs
    # under the host (older BE) python interpreter with sys.path pointing at the target
    # (newer BE) dist-packages, so the target's truenas_os .so — built against the target
    # BE's python ABI and potentially relying on kernel features the host kernel lacks —
    # may fail to load (ImportError) or bind (AttributeError). This fallback drops the
    # openat2 symlink-race protection the upstream version provides; that is acceptable
    # here because the target rootfs has just been unsquashed and is not under attacker
    # influence at this point in the upgrade flow.
    if mode not in ("w", "wb"):
        raise ValueError(f'{mode}: invalid mode. Only "w" and "wb" are supported.')

    if tmppath is None:
        tmppath = os.path.dirname(target)

    fd, tmp_name = tempfile.mkstemp(dir=tmppath, prefix=".atomic_write_")
    committed = False
    try:
        with os.fdopen(fd, mode) as f:
            os.fchown(f.fileno(), uid, gid)
            os.fchmod(f.fileno(), perms)
            yield f
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
        committed = True
    finally:
        if not committed:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)


def update_zfs_default(root, readonly_rootfs):
    # Older versions wrote ZFS_INITRD_POST_MODPROBE_SLEEP=15 here when the boot pool was on
    # USB, to let USB enumeration finish before zpool import. USB boot is no longer supported,
    # so this function only strips the line from upgraded installs; can be removed once
    # versions that wrote it are past EOL.
    zfs_config_path = os.path.join(root, "etc/default/zfs")
    with open(zfs_config_path) as f:
        original_config = f.read()
        lines = original_config.rstrip().split("\n")

    zfs_var_name = "ZFS_INITRD_POST_MODPROBE_SLEEP"
    lines = [line for line in lines if not line.startswith(f"{zfs_var_name}=")]

    new_config = "\n".join(lines) + "\n"
    if new_config != original_config:
        readonly_rootfs.make_writeable()
        with atomic_write(zfs_config_path, "w") as f:
            f.write(new_config)

        return True

    return False


def get_current_gpu_pci_ids(database):
    adv_config = query_config_table("system_advanced", database, "adv_")
    to_isolate = [gpu for gpu in get_gpus() if gpu["addr"]["pci_slot"] in adv_config.get("isolated_gpu_pci_ids", [])]
    return [dev["pci_slot"] for gpu in to_isolate for dev in gpu["devices"]]


def update_pci_module_files(root, config):
    # This method is (and must be) called when root is writeable

    def get_path(p):
        return os.path.join(root, p)

    pci_slots = config["pci_ids"]
    for path in map(
        get_path, [
            'etc/initramfs-tools/scripts/init-top/truenas_bind_vfio.sh',
            "etc/initramfs-tools/modules",
            "etc/modules",
            "etc/modprobe.d/kvm.conf",
            "etc/modprobe.d/nvidia.conf",
        ]
    ):
        with contextlib.suppress(Exception):
            os.unlink(path)

    os.makedirs(get_path("etc/initramfs-tools"), exist_ok=True)
    os.makedirs(get_path("etc/modprobe.d"), exist_ok=True)

    if not pci_slots:
        for path in map(
            get_path, [
                "etc/initramfs-tools/modules",
                "etc/modules",
            ]
        ):
            with atomic_write(path, "w", tmppath=get_path("etc")):
                pass

        return

    for path in map(get_path, ["etc/initramfs-tools/modules", "etc/modules"]):
        with atomic_write(path, "w", tmppath=get_path("etc")) as f:
            f.write(textwrap.dedent("""\
                vfio
                vfio_iommu_type1
                vfio_virqfd
                vfio_pci
            """))

    with atomic_write(get_path("etc/modprobe.d/kvm.conf"), "w", tmppath=get_path("etc")) as f:
        f.write("options kvm ignore_msrs=1\n")

    with atomic_write(get_path("etc/modprobe.d/nvidia.conf"), "w", tmppath=get_path("etc")) as f:
        f.write(textwrap.dedent("""\
            softdep nouveau pre: vfio-pci
            softdep nvidia pre: vfio-pci
            softdep nvidia* pre: vfio-pci
        """))

    with atomic_write(
        get_path("etc/initramfs-tools/scripts/init-top/truenas_bind_vfio.sh"), "w",
        tmppath=get_path("etc"),
        perms=0o755
    ) as f:
        f.write(textwrap.dedent(f"""\
            #!/bin/sh
            PREREQS=""
            DEVS="{' '.join(pci_slots)}"
            for DEV in $DEVS;
              do echo "vfio-pci" > /sys/bus/pci/devices/$DEV/driver_override
            done
            modprobe -i vfio-pci
        """))


def update_pci_initramfs_config(root, readonly_rootfs, database):
    initramfs_config_path = os.path.join(root, "boot/initramfs_config.json")
    initramfs_config = {
        "pci_ids": get_current_gpu_pci_ids(database),
    }
    original_config = None
    if os.path.exists(initramfs_config_path):
        with open(initramfs_config_path, "r") as f:
            original_config = json.loads(f.read())

    if initramfs_config != original_config:
        readonly_rootfs.make_writeable()

        with atomic_write(initramfs_config_path, "w", tmppath=os.path.join(root, "boot")) as f:
            f.write(json.dumps(initramfs_config))

        update_pci_module_files(root, initramfs_config)
        return True

    return False


def update_zfs_module_config(root, readonly_rootfs, database):
    options = []
    for tunable in query_table("system_tunable", database, "tun_"):
        if tunable["type"] != "ZFS":
            continue
        if not tunable["enabled"]:
            continue

        options.append(f"{tunable['var']}={tunable['value']}")

    if options:
        config = f"options zfs {' '.join(options)}\n"
    else:
        config = None

    config_path = os.path.join(root, "etc", "modprobe.d", "zfs.conf")
    try:
        with open(config_path) as f:
            existing_config = f.read()
    except FileNotFoundError:
        existing_config = None

    if existing_config != config:
        readonly_rootfs.make_writeable()

        if config is None:
            os.unlink(config_path)
        else:
            with atomic_write(config_path, "w", tmppath=os.path.join(root, "etc")) as f:
                f.write(config)

        return True

    return False


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description=(
            "Regenerate the initramfs for a target TrueNAS boot environment (BE). TrueNAS "
            "installs each version into its own BE; this script can run in several "
            "contexts: from a fresh-install ISO targeting a newly-extracted BE, from an "
            "existing TrueNAS upgrading to a new BE, or against the currently-running BE "
            "for a runtime regen. The path to the target BE's rootfs is passed as the "
            "`chroot` argument. When the target differs from the executing environment "
            "the target BE's python dist-packages directory is prepended to `sys.path` "
            "so that imports of libraries shipped with the target BE (e.g. "
            "`truenas_pylibvirt`, `truenas_os_pyutils`, `middlewared`) resolve against "
            "the target BE's modules rather than the host's, and `chroot` is used to run "
            "`update-initramfs` against the target BE."
        ),
    )
    p.add_argument(
        "chroot", nargs=1,
        help=(
            "Path to the target boot environment's rootfs. During fresh installs and "
            "upgrades this is the mountpoint of the newly-extracted target BE; pass `/` "
            "to operate on the currently-running BE."
        ),
    )
    p.add_argument(
        "--database", "-d", default="",
        help=(
            "Path to the TrueNAS configuration database to read configuration from. "
            "Defaults to the database located inside the target BE's rootfs."
        ),
    )
    p.add_argument(
        "--force", "-f", action="store_true",
        help=(
            "Regenerate the initramfs in the target BE for every kernel even if no "
            "configuration changed."
        ),
    )
    args = p.parse_args()
    root = args.chroot[0]
    if root != "/":
        sys.path.insert(0, os.path.join(root, "usr/lib/python3/dist-packages"))

    # BEGIN LAZY IMPORTS
    # ------------------
    from truenas_pylibvirt.utils.gpu import get_gpus

    try:
        from truenas_os_pyutils.io import atomic_write
    except (ImportError, AttributeError):
        atomic_write = atomic_write_fallback

    from middlewared.utils.db import FREENAS_DATABASE, query_config_table, query_table
    from middlewared.utils.rootfs import ReadonlyRootfsManager
    # ------------------
    # END LAZY IMPORTS

    with ReadonlyRootfsManager(root) as readonly_rootfs:
        try:
            database = args.database or os.path.join(root, FREENAS_DATABASE[1:])

            adv_config = query_config_table("system_advanced", database, "adv_")
            debug_kernel = adv_config["debugkernel"]

            update_required = any((
                update_zfs_default(root, readonly_rootfs),
                update_pci_initramfs_config(root, readonly_rootfs, database),
                update_zfs_module_config(root, readonly_rootfs, database),
            ))

            for kernel in os.listdir(f"{root}/boot"):
                if not kernel.startswith("vmlinuz-"):
                    continue

                kernel_name = kernel.removeprefix("vmlinuz-")
                if "debug" in kernel_name and not debug_kernel:
                    continue

                if args.force or update_required or not os.path.exists(f"{root}/boot/initrd.img-{kernel_name}"):
                    readonly_rootfs.make_writeable()
                    subprocess.run(["chroot", root, "update-initramfs", "-k", kernel_name, "-u"], check=True)
        except Exception:
            logger.error("Failed to update initramfs", exc_info=True)
            exit(2)

    # We give out an exit code of 1 when initramfs has been updated as we require a reboot of the system for the
    # changes to have an effect. This caters to the case of uploading a database. Otherwise, we give an exit code
    # of 0 and in case of erring out
    exit(int(update_required))
