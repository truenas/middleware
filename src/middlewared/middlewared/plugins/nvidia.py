import contextlib
import os
import shutil
import subprocess
import tempfile

import requests

from middlewared.service import job, Service
from middlewared.utils.gpu import get_gpus
from middlewared.utils.rootfs import ReadonlyRootfsManager

HEADERS = {"User-Agent": "curl/7.88.1"}


class NvidiaService(Service):
    class Config:
        private = True

    def present(self):
        adv_config = self.middleware.call_sync("system.advanced.config")

        for gpu in get_gpus():
            if gpu["addr"]["pci_slot"] in adv_config["isolated_gpu_pci_ids"]:
                continue

            if gpu["vendor"] == "NVIDIA":
                return True

        return False

    def installed(self):
        with open("/proc/modules") as f:
            lines = f.readlines()

        for line in lines:
            if line.split()[0] == "nvidia":
                return True

        return False

    @job(lock="nvidia", description=lambda *args: "Installing NVIDIA drivers")
    def install(self, job, start_docker=None):
        if self.installed():
            return

        self.middleware.call_sync("network.general.will_perform_activity", "catalog")

        with ReadonlyRootfsManager() as rrm:
            job.set_progress(0, "Temporarily making root filesystem writeable")
            rrm.make_writeable()

            job.set_progress(1, "Adding NVIDIA repository")
            self._add_nvidia_repository()

            with self._install_packages(
                job,
                ["gcc", "make", "pkg-config"],
                ["libvulkan1", "nvidia-container-toolkit", "vulkan-validationlayers"],
            ):
                # `/tmp` is `nonexec`, we'll have to use another directory
                with tempfile.TemporaryDirectory(dir="/root") as td:
                    path = self._download(job, td)

                    self._install_driver(job, td, path)

        if start_docker or self.middleware.call_sync("service.started", "docker"):
            job.set_progress(90, "Restarting docker")
            self.middleware.call_sync("service.restart", "docker")

    def _add_nvidia_repository(self):
        if not os.path.exists("/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"):
            r = requests.get("https://nvidia.github.io/libnvidia-container/gpgkey")
            r.raise_for_status()

            subprocess.run(["gpg", "--dearmor", "-o", "/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"],
                           input=r.content, capture_output=True, check=True)

        with open("/etc/apt/sources.list.d/nvidia-container-toolkit.list", "w") as f:
            f.write("deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] "
                    "https://nvidia.github.io/libnvidia-container/stable/deb/$(ARCH) /")

    @contextlib.contextmanager
    def _install_packages(self, job, temporary, permanent):
        kwargs = dict(capture_output=True, check=True, text=True)

        try:
            job.set_progress(5, "Updating apt cache")
            subprocess.run(["apt", "update"], **kwargs)

            try:
                job.set_progress(10, "Installing apt packages")
                subprocess.run(["apt", "-y", "install"] + temporary + permanent, **kwargs)

                yield
            finally:
                job.set_progress(80, "Removing apt packages")
                subprocess.run(["apt", "-y", "remove"] + temporary, **kwargs)
                subprocess.run(["apt", "-y", "autoremove"], **kwargs)
        finally:
            shutil.rmtree("/var/cache/apt", ignore_errors=True)

    def _download(self, job, path):
        prefix = "https://download.nvidia.com/XFree86/Linux-x86_64"

        r = requests.get(f"{prefix}/latest.txt", headers=HEADERS, timeout=10)
        r.raise_for_status()
        version = r.text.split()[0]
        filename = f"NVIDIA-Linux-x86_64-{version}-no-compat32.run"
        result = f"{path}/{filename}"

        with requests.get(f"{prefix}/{version}/{filename}", headers=HEADERS, stream=True, timeout=10) as r:
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
