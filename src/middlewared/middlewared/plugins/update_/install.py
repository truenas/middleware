import errno
import json
import logging
import os
import subprocess
import time

import humanfriendly

from middlewared.service import CallError, private, Service
from middlewared.utils import osc

logger = logging.getLogger(__name__)

run_kw = dict(check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="ignore")


class UpdateService(Service):
    @private
    def install_scale(self, mounted, progress_callback):
        with open(os.path.join(mounted, "manifest.json")) as f:
            manifest = json.load(f)

        boot_pool_name = self.middleware.call_sync("boot.pool_name")
        self.middleware.call_sync("update.ensure_free_space", boot_pool_name, manifest["size"])

        for file, checksum in manifest["checksums"].items():
            progress_callback(0, f"Verifying {file}")
            if osc.IS_FREEBSD:
                our_checksum = subprocess.run(["sha1", os.path.join(mounted, file)], **run_kw).stdout.split()[-1]
            else:
                our_checksum = subprocess.run(["sha1sum", os.path.join(mounted, file)], **run_kw).stdout.split()[0]
            if our_checksum != checksum:
                raise CallError(f"Checksum mismatch for {file!r}: {our_checksum} != {checksum}")

        command = {
            "disks": self.middleware.call_sync("boot.get_disks"),
            "json": True,
            "old_root": "/",
            "pool_name": boot_pool_name,
            "src": mounted,
        }

        if osc.IS_FREEBSD:
            command["devices"] = self.middleware.call_sync("zfs.pool.get_devices", boot_pool_name)

        p = subprocess.Popen(
            ["python3", "-m", "truenas_install"], cwd=mounted, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="ignore",
        )
        p.stdin.write(json.dumps(command))
        p.stdin.close()
        stderr = ""
        error = None
        for line in iter(p.stdout.readline, ""):
            try:
                data = json.loads(line)
            except ValueError:
                stderr += line
            else:
                if "progress" in data and "message" in data:
                    progress_callback(data["progress"], data["message"])
                elif "error" in data:
                    error = data["error"]
                else:
                    raise ValueError(f"Invalid truenas_install JSON: {data!r}")
        p.wait()
        if p.returncode != 0:
            if error is not None:
                raise CallError(error)
            else:
                raise CallError(stderr)

    @private
    def ensure_free_space(self, pool_name, size):
        space_left = self._space_left(pool_name)

        if space_left > size:
            return

        for bootenv in reversed(self.middleware.call_sync(
            "bootenv.query",
            [
                ["keep", "=", False],
                ["mountpoint", "=", "-"],
                ["activated", "=", False],
            ],
            {"order_by": ["created"]},
        )):
            space_left_before_prune = space_left

            logger.info("Pruning %r", bootenv["id"])
            self.middleware.call_sync("bootenv.delete", bootenv["id"])

            be_size = bootenv["rawspace"]
            if be_size is None:
                be_size = 0

            for i in range(10):
                space_left = self._space_left(pool_name)

                if space_left > size:
                    return

                freed_space = space_left - space_left_before_prune
                if freed_space >= be_size * 0.5:
                    return

                logger.debug("Only freed %d bytes of %d, waiting for deferred operation to complete...", freed_space,
                             be_size)
                time.sleep(1)

        raise CallError(
            f"Insufficient disk space available on {pool_name} ({humanfriendly.format_size(space_left)}). "
            f"Need {humanfriendly.format_size(size)}",
            errno.ENOSPC,
        )

    def _space_left(self, pool_name):
        pool = self.middleware.call_sync("zfs.pool.query", [["name", "=", pool_name]], {"get": True})
        return pool["properties"]["free"]["parsed"]
