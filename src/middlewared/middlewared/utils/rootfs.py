import contextlib
from dataclasses import dataclass
from functools import cached_property
import json
import os
import subprocess

from middlewared.utils.filesystem import stat_x
from middlewared.utils.mount import getmntinfo


@dataclass
class ReadonlyState:
    initial: bool
    current: bool


@dataclass
class Dataset:
    name: str
    mountpoint: str
    readonly: ReadonlyState

    @cached_property
    def readonly_source(self):
        return subprocess.run(
            ["zfs", "get", "-H", "-o", "source", "readonly", self.name],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()


class ReadonlyRootfsManager:
    def __init__(self, root="/"):
        self.root = root

        self.initialized = False
        self.datasets: dict[str, Dataset] = {}
        self.use_functioning_dpkg_sysext = False

    def __enter__(self):
        return self

    def make_writeable(self):
        self._initialize()

        self._set_state({
            name: False
            for name, dataset in self.datasets.items()
            if dataset.readonly.current
        })
        self._set_dpkg_sysext_state(True)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.initialized:
            return

        self._set_state({
            name: dataset.readonly.initial
            for name, dataset in self.datasets.items()
            if dataset.readonly.current != dataset.readonly.initial
        })
        self._set_dpkg_sysext_state(False)

    def _initialize(self):
        if self.initialized:
            return

        with open(os.path.join(self.root, "conf/truenas_root_ds.json"), "r") as f:
            conf = json.loads(f.read())

        usr_ds = next((i for i in conf if i["fhs_entry"]["name"] == "usr"))["ds"]
        for dataset, name in [
            ("", usr_ds.rsplit("/", 1)[0]),
            ("usr", usr_ds),
        ]:
            mountpoint = os.path.realpath("/".join(filter(None, (self.root, dataset))))

            if mountpoint == "/usr":
                # We make `/usr` writeable only to be able to temporary enable `dpkg` (`update-initramfs` needs it).
                # If we are on live system, it's better to use `systemd-sysext`
                self.use_functioning_dpkg_sysext = True
                continue

            st_mnt_id = stat_x.statx(mountpoint).stx_mnt_id
            readonly = "RO" in getmntinfo(mnt_id=st_mnt_id)[st_mnt_id]["super_opts"]

            self.datasets[dataset] = Dataset(name, mountpoint, ReadonlyState(readonly, readonly))

        self.initialized = True

    def _set_state(self, state: dict[str, bool]):
        if state.get("usr") is True:
            self._handle_usr(True)

        for name, readonly in state.items():
            # Do not change `readonly` property when we're running in the installer, and it was not set yet
            if self.datasets[name].readonly_source != "local":
                continue

            subprocess.run(
                ["zfs", "set", f"readonly={'on' if readonly else 'off'}", self.datasets[name].name],
                capture_output=True,
                check=True,
                text=True,
            )
            subprocess.run(
                ["mount", "-o", f"{'ro' if readonly else 'rw'},remount", self.datasets[name].mountpoint],
                capture_output=True,
                check=True,
                text=True,
            )
            self.datasets[name].readonly.current = readonly

        if state.get("usr") is False:
            self._handle_usr(False)

    def _handle_usr(self, readonly):
        binaries = (
            # Some initramfs scripts use `dpkg --print-architecture` or similar calls
            "dpkg",
        )
        if readonly:
            for binary in binaries:
                os.chmod(os.path.join(self.root, f"usr/bin/{binary}"), 0o644)
                with contextlib.suppress(FileNotFoundError):
                    os.rename(os.path.join(self.root, f"usr/local/bin/{binary}.bak"),
                              os.path.join(self.root, f"usr/local/bin/{binary}"))
        else:
            for binary in binaries:
                os.chmod(os.path.join(self.root, f"usr/bin/{binary}"), 0o755)
                with contextlib.suppress(FileNotFoundError):
                    os.rename(os.path.join(self.root, f"usr/local/bin/{binary}"),
                              os.path.join(self.root, f"usr/local/bin/{binary}.bak"))

    def _set_dpkg_sysext_state(self, enabled):
        if self.use_functioning_dpkg_sysext:
            os.makedirs("/run/extensions", exist_ok=True)
            sysext_dst = "/run/extensions/functioning-dpkg.raw"
            if enabled:
                with contextlib.suppress(FileExistsError):
                    os.symlink("/usr/share/truenas/sysext-extensions/functioning-dpkg.raw", sysext_dst)
            else:
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(sysext_dst)

            subprocess.run(["systemd-sysext", "refresh"], capture_output=True, check=True, text=True)
