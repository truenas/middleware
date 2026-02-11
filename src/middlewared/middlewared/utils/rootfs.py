import contextlib
from dataclasses import dataclass
from functools import cached_property
import json
import os
import subprocess
from types import TracebackType
from typing import Any, Self

from middlewared.utils.mount import statmount


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
    def readonly_source(self) -> str:
        return subprocess.run(
            ["zfs", "get", "-H", "-o", "source", "readonly", self.name],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()


class ReadonlyRootfsManager:
    def __init__(self, root: str = "/", force_usr_rw: bool = False):
        self.root = root
        self.initialized = False
        self.datasets: dict[str, Dataset] = {}
        self.use_functioning_dpkg_sysext = False
        self.force_usr_rw = force_usr_rw

    def __enter__(self) -> Self:
        return self

    def make_writeable(self) -> None:
        self._initialize()
        self._set_state({
            name: False
            for name, dataset in self.datasets.items()
            if dataset.readonly.current
        })
        self._set_dpkg_sysext_state(True)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None
    ) -> None:
        if not self.initialized:
            return

        self._set_state({
            name: dataset.readonly.initial
            for name, dataset in self.datasets.items()
            if dataset.readonly.current != dataset.readonly.initial
        })
        self._set_dpkg_sysext_state(False)

    def _initialize(self) -> None:
        if self.initialized:
            return

        with open(os.path.join(self.root, "conf/truenas_root_ds.json"), "r") as f:
            conf: list[dict[str, Any]] = json.loads(f.read())

        usr_ds: str = next((i for i in conf if i["fhs_entry"]["name"] == "usr"))["ds"]
        for dataset, name in [
            ("", usr_ds.rsplit("/", 1)[0]),
            ("usr", usr_ds),
        ]:
            mountpoint = os.path.realpath("/".join(filter(None, (self.root, dataset))))
            if mountpoint == "/usr" and not self.force_usr_rw:
                # 1. We make `/usr` writeable only to be able to
                #   temporary enable `dpkg` (`update-initramfs` needs it).
                # 2. OR someone is using this context manager with `force_usr_rw`
                #   set to True. This is needed, for example, when support team
                #   flashes a Chelsio NIC to a different mode. Chelsio's provided
                #   script needs write access to firmware files located in /lib.
                #
                # Otherwise, if we are on live system, it's better
                # to use `systemd-sysext`
                self.use_functioning_dpkg_sysext = True
                continue

            readonly = "RO" in statmount(path=mountpoint)["mount_opts"]

            self.datasets[dataset] = Dataset(name, mountpoint, ReadonlyState(readonly, readonly))

        self.initialized = True

    def _set_state(self, state: dict[str, bool]) -> None:
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

    def _handle_usr(self, readonly: bool) -> None:
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

    def _set_dpkg_sysext_state(self, enabled: bool) -> None:
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
