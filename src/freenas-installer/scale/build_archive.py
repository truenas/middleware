# -*- coding=utf-8 -*-
import argparse
import contextlib
import glob
import json
import logging
import os
import shutil
import subprocess
import tempfile
import textwrap

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if os.getuid() != 0:
        raise RuntimeError("This script must be ran by root")

    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-rootfs", action="store_true")
    parser.add_argument("version")
    args = parser.parse_args()

    os.chdir(os.path.normpath(os.path.dirname(__file__)))

    if not args.skip_rootfs:
        with contextlib.suppress(FileNotFoundError):
            os.unlink("/usr/share/debootstrap/scripts/truenas")
        subprocess.run("ln -s /usr/share/debootstrap/scripts/bullseye /usr/share/debootstrap/scripts/truenas",
                       check=True, shell=True)

        subprocess.run("rm -rf rootfs", check=True, shell=True)

        subprocess.run("mkdir rootfs", check=True, shell=True)
        subprocess.run("debootstrap --arch amd64 truenas rootfs http://apt.tn.ixsystems.com/truenas/unstable",
                       check=True, shell=True)

        subprocess.run("mount -t proc none rootfs/proc", check=True, shell=True)
        try:
            subprocess.run("mount -t sysfs none rootfs/sys", check=True, shell=True)
            try:
                # scst installer calls depmod, but current running kernel might not match
                os.rename("rootfs/sbin/depmod", "rootfs/tmp/depmod")
                with open("rootfs/sbin/depmod", "w") as f:
                    f.write(textwrap.dedent("""\
                        #!/bin/sh
                        if [ $# -eq 0 ]; then
                            exec /tmp/depmod `ls -1 /lib/modules`
                        else
                            exec /tmp/depmod "$@"
                        fi
                    """))
                os.chmod("rootfs/sbin/depmod", 0o755)

                os.rename("rootfs/bin/uname", "rootfs/bin/uname.orig")
                with open("rootfs/bin/uname", "w") as f:
                    f.write(textwrap.dedent("""\
                        #!/bin/sh
                        if [ x"$1" = x"-r" ]; then
                            ls -1 /lib/modules
                        else
                            exec uname.orig "$@"
                        fi
                    """))
                os.chmod("rootfs/bin/uname", 0o755)

                try:
                    subprocess.run(
                        "chroot rootfs apt-get -y install grub2 truenas usrmerge zfs-initramfs",
                        check=True, shell=True, env={"DEBIAN_FRONTEND": "noninteractive"},
                    )
                finally:
                    os.rename("rootfs/bin/uname.orig", "rootfs/bin/uname")
                    os.rename("rootfs/tmp/depmod", "rootfs/sbin/depmod")
            finally:
                subprocess.run("umount rootfs/sys", check=True, shell=True)
        finally:
            subprocess.run("umount rootfs/proc", check=True, shell=True)

        for file in ["group", "passwd"]:
            cmd = [
                "diff", "-u", f"rootfs/etc/{file}",
                f"rootfs/usr/lib/python3/dist-packages/middlewared/assets/account/builtin/linux/{file}"
            ]
            run = subprocess.run(cmd, stdout=subprocess.PIPE, encoding="utf-8", errors="ignore")
            if run.returncode not in [0, 1]:
                raise subprocess.CalledProcessError(run.returncode, cmd, run.stdout)

            diff = "\n".join(run.stdout.split("\n")[3])
            if any(line.startswith("-") for line in diff.split("\n")):
                raise ValueError(f"Invalid {file!r} assest:\n{diff}")

        with open(os.path.join("rootfs/data/manifest.json"), "w") as f:
            json.dump({
                "train": "TrueNAS-SCALE-13.0-STABLE",
                "version": args.version,
            }, f)

        subprocess.run("rm rootfs.sqsh", shell=True)
        subprocess.run(f"mksquashfs rootfs rootfs.sqsh", check=True, shell=True)

    with tempfile.TemporaryDirectory() as output:
        shutil.copyfile("rootfs.sqsh", f"{output}/rootfs.sqsh")

        shutil.copytree("truenas_update", os.path.join(output, "truenas_update"))

        checksums = {}
        for root, dirs, files in os.walk(output):
            for file in files:
                abspath = os.path.join(root, file)
                checksums[os.path.relpath(abspath, output)] = subprocess.run(
                    f"sha1sum {abspath}",
                    check=True, shell=True, stdout=subprocess.PIPE, encoding="utf-8", errors="ignore",
                ).stdout.split()[0]

        with open(os.path.join(output, "manifest.json"), "w") as f:
            f.write(json.dumps({
                "version": args.version,
                "checksums": checksums,
                "kernel_version": glob.glob("rootfs/boot/vmlinuz-*")[0].split("/")[-1][len("vmlinuz-"):],
            }))

        subprocess.run("rm update.sqsh", shell=True)
        subprocess.run(f"mksquashfs {output} update.sqsh", check=True, shell=True)
