from typing import Any

from middlewared.service import Service

from . import sysctl_info as _sysctl

__all__ = ('SysctlService',)


class SysctlService(Service):

    class Config:
        private = True

    async def get_value(self, sysctl_name: str) -> str:
        return await _sysctl.get_value(sysctl_name)

    def store_default_arc_max(self) -> int:
        return _sysctl.store_default_arc_max()

    def get_default_arc_max(self) -> int:
        return _sysctl.get_default_arc_max()

    def get_arc_max(self) -> int:
        return _sysctl.get_arc_max()

    def get_arc_min(self) -> int:
        return _sysctl.get_arc_min()

    async def get_pagesize(self) -> int:
        return await _sysctl.get_pagesize()

    def get_arcstats(self) -> dict[str, Any]:
        return _sysctl.get_arcstats()

    def get_arcstats_size(self) -> int:
        return _sysctl.get_arcstats_size()

    async def set_value(self, key: str, value: str | int) -> None:
        await _sysctl.set_value(key, value)

    def write_to_file(self, path: str, value: int) -> None:
        _sysctl.write_to_file(path, value)

    def set_arc_max(self, value: int) -> None:
        _sysctl.set_arc_max(value)

    def set_zvol_volmode(self, value: int) -> None:
        _sysctl.set_zvol_volmode(value)
