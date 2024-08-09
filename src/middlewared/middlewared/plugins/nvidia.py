import contextlib
import os
import shutil
import subprocess
import tempfile

import requests

from middlewared.service import job, Service
from middlewared.utils.rootfs import ReadonlyRootfsManager


class NvidiaService(Service):
    class Config:
        private = True

    @job(lock="nvidia")
    def install(self, job):
        self.middleware.call_sync("network.general.will_perform_activity", "catalog")

        with ReadonlyRootfsManager() as rrm:
            job.set_progress(0, "Temporarily making root filesystem writeable")
            rrm.make_writeable()

            with self._install_packages(
                job,
                ["gcc", "make", "pkg-config"],
                ["vulkan-validationlayers", "libvulkan1"],
            ):
                # `/tmp` is `nonexec`, we'll have to use another directory
                with tempfile.TemporaryDirectory(dir="/root") as td:
                    path = self._download(job, td)

                    self._install_driver(job, td, path)

    @contextlib.contextmanager
    def _install_packages(self, job, temporary, permanent):
        kwargs = dict(capture_output=True, check=True, text=True)

        try:
            job.set_progress(1, "Updating apt cache")
            subprocess.run(["apt", "update"], **kwargs)

            try:
                job.set_progress(10, "Installing apt packages")
                subprocess.run(["apt", "-y", "install"] + temporary + permanent, **kwargs)

                yield
            finally:
                job.set_progress(95, "Removing apt packages")
                subprocess.run(["apt", "-y", "remove"] + temporary, **kwargs)
                subprocess.run(["apt", "-y", "autoremove"], **kwargs)
        finally:
            shutil.rmtree("/var/cache/apt", ignore_errors=True)

    def _download(self, job, path):
        prefix = "https://download.nvidia.com/XFree86/Linux-x86_64"
        headers = {"User-Agent": "curl/7.88.1"}

        r = requests.get(f"{prefix}/latest.txt", headers=headers, timeout=10)
        r.raise_for_status()
        version = r.text.split()[0]
        filename = f"NVIDIA-Linux-x86_64-{version}-no-compat32.run"
        result = f"{path}/{filename}"

        with requests.get(f"{prefix}/{version}/{filename}", headers=headers, stream=True, timeout=10) as r:
            r.raise_for_status()

            progress = 0
            total = int(r.headers["Content-Length"])
            with open(result, "wb") as f:
                for chunk in r.iter_content(chunk_size=24 * 1024 * 1024):
                    job.set_progress(
                        10 + int(progress / total * 10),
                        "Downloading drivers",
                    )

                    progress += len(chunk)
                    f.write(chunk)

        os.chmod(result, 0o755)
        return result

    def _install_driver(self, job, td, path):
        job.set_progress(20, "Installing driver")

        subprocess.run([path, "--tmpdir", td, "-s"], capture_output=True, check=True, text=True)
