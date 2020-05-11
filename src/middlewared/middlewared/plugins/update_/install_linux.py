import json
import logging
import os
import re
import subprocess
import tempfile

from middlewared.service import CallError, private, Service

from .utils import SCALE_MANIFEST_FILE, can_update
from .utils_linux import mount_update

logger = logging.getLogger(__name__)

RE_UNSQUASHFS_PROGRESS = re.compile(r"\[.+\]\s+(?P<extracted>[0-9]+)/(?P<total>[0-9]+)\s+(?P<progress>[0-9]+)%")
run_kw = dict(check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="ignore")


class UpdateService(Service):
    @private
    def install_impl(self, job, location):
        self._install(
            os.path.join(location, "update.sqsh"),
            lambda progress, description: job.set_progress((0.5 + 0.5 * progress) * 100, description),
        )

    @private
    def install_manual_impl(self, job, path, dest_extracted):
        self._install(
            path,
            lambda progress, description: job.set_progress((0.5 + 0.5 * progress) * 100, description),
        )

    def _install(self, path, progress_callback):
        with open(SCALE_MANIFEST_FILE) as f:
            old_manifest = json.load(f)

        progress_callback(0, "Reading update file")
        with mount_update(path) as mounted:
            with open(os.path.join(mounted, "manifest.json")) as f:
                manifest = json.load(f)

            old_version = old_manifest["version"]
            new_version = manifest["version"]
            if not can_update(old_version, new_version):
                raise CallError(f'Unable to downgrade from {old_version} to {new_version}')

            for file, checksum in manifest["checksums"].items():
                progress_callback(0, f"Verifying {file}")
                our_checksum = subprocess.run(["sha1sum", os.path.join(mounted, file)], **run_kw).stdout.split()[0]
                if our_checksum != checksum:
                    raise CallError(f"Checksum mismatch for {file!r}: {our_checksum} != {checksum}")

            pool_name = self.middleware.call_sync("boot.pool_name")
            dataset_name = f"{pool_name}/ROOT/{manifest['version']}"

            progress_callback(0, "Creating dataset")
            self.middleware.call_sync("zfs.dataset.create", {
                "name": dataset_name,
                "properties": {
                    "mountpoint": "legacy",
                    "truenas:kernel_version": manifest["kernel_version"],
                },
            })
            try:
                with tempfile.TemporaryDirectory() as root:
                    subprocess.run(["mount", "-t", "zfs", dataset_name, root])
                    try:
                        progress_callback(0, "Extracting...")
                        cmd = [
                            "unsquashfs",
                            "-d", root,
                            "-f",
                            "-da", "16",
                            "-fr", "16",
                            os.path.join(mounted, "rootfs.sqsh"),
                        ]
                        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        stdout = ""
                        buffer = b""
                        for char in iter(lambda: p.stdout.read(1), b""):
                            buffer += char
                            if char == b"\n":
                                stdout += buffer.decode("utf-8", "ignore")
                                buffer = b""

                            if buffer and buffer[0:1] == b"\r" and buffer[-1:] == b"%":
                                if m := RE_UNSQUASHFS_PROGRESS.match(buffer[1:].decode("utf-8", "ignore")):
                                    progress_callback(
                                        int(m.group("extracted")) / int(m.group("total")) * 0.9,
                                        "Extracting",
                                    )

                                    buffer = b""

                        p.wait()
                        if p.returncode != 0:
                            raise subprocess.CalledProcessError(p.returncode, cmd, stdout)

                        progress_callback(0.9, "Performing post-install tasks")
                        update = json.dumps({
                            "pool_name": pool_name,
                            "dataset_name": dataset_name,
                            "disks": self.middleware.call_sync("boot.get_disks"),
                            "root": root,
                        })
                        subprocess.run(["python3", "-m", "truenas_update"], cwd=mounted, input=update, **run_kw)
                    finally:
                        subprocess.run(["umount", root])
            except Exception:
                self.middleware.call_sync("zfs.dataset.delete", dataset_name)
                raise
