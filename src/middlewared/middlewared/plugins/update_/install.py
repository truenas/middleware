import errno
import hashlib
import json
import logging
import os
import subprocess
import time

from middlewared.service import CallError, private, Service
from middlewared.utils.size import format_size

logger = logging.getLogger(__name__)

run_kw = dict(check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="ignore")
STARTING_INSTALLER = "Starting installer"


def get_hash(file_path, digest="sha1"):
    with open(file_path, 'rb') as f:
        return hashlib.file_digest(f, digest).hexdigest()


class UpdateService(Service):
    @private
    def install_scale(self, mounted, progress_callback, options):
        raise_warnings = options.pop("raise_warnings", True)

        with open(os.path.join(mounted, "manifest.json")) as f:
            manifest = json.load(f)

        boot_pool_name = self.middleware.call_sync("boot.pool_name")
        self.middleware.call_sync("update.ensure_free_space", boot_pool_name, manifest["size"])

        for file, checksum in manifest["checksums"].items():
            progress_callback(0, f"Verifying {file}")
            file_path = os.path.join(mounted, file)
            our_checksum = get_hash(file_path)
            if our_checksum != checksum:
                # eventually we will use sha256
                our_checksum = get_hash(file_path, digest="sha256")
                if our_checksum != checksum:
                    raise CallError(f"Checksum mismatch for {file!r}: {our_checksum} != {checksum}")

        progress_callback(0, "Running pre-checks")
        warning = self._execute_truenas_install(mounted, {
            "json": True,
            "old_root": "/",
            "precheck": True,
        }, progress_callback)
        if warning and raise_warnings:
            raise CallError(warning, errno.EAGAIN)

        progress_callback(0, STARTING_INSTALLER)
        command = {
            "disks": self.middleware.call_sync("boot.get_disks"),
            "json": True,
            "old_root": "/",
            "pool_name": boot_pool_name,
            "src": mounted,
            **options,
        }
        self._execute_truenas_install(mounted, command, progress_callback)

    def _execute_truenas_install(self, cwd, command, progress_callback):
        p = subprocess.Popen(
            ["python3", "-m", "truenas_install"], cwd=cwd, stdin=subprocess.PIPE,
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

        if error is not None:
            result = error
        else:
            result = stderr

        if p.returncode != 0:
            raise CallError(result or f"Abnormal installer process termination with code {p.returncode}")
        else:
            return result

    @private
    def ensure_free_space(self, pool_name, size):
        space_left = self._space_left(pool_name)
        if space_left > size:
            return

        filters = [
            # ignore BE that is explicitly marked to be kept
            ["keep", "=", False],
            # ignore current BE
            ["active", "=", False],
            # ignore active BE on next reboot
            ["activated", "=", False],
        ]
        # ascending order (i.e. oldest comes first)
        opts = {"order_by": ["created"]}
        for be in self.middleware.call_sync(
            "boot.environment.query", filters, opts
        ):
            space_left_before_prune = space_left
            logger.info("Pruning %r", be["id"])
            self.middleware.call_sync("boot.environment.destroy", {"id": be["id"]})

            be_size = be["used_bytes"]
            for i in range(10):
                space_left = self._space_left(pool_name)
                if space_left > size:
                    return

                freed_space = space_left - space_left_before_prune
                if freed_space >= be_size * 0.5:
                    return

                logger.debug(
                    "Only freed %d bytes of %d, waiting for deferred operation to complete...",
                    freed_space,
                    be_size
                )
                time.sleep(1)

        raise CallError(
            f"Insufficient disk space available on {pool_name} ({format_size(space_left)}). "
            f"Need {format_size(size)}",
            errno.ENOSPC,
        )

    def _space_left(self, pool_name):
        return self.middleware.call_sync(
            'zfs.resource.query_impl', {'paths': [pool_name], 'properties': ['available']}
        )[0]['properties']['available']['value']
