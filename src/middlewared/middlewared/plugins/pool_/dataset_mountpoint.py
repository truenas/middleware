from middlewared.schema import accepts, returns, Bool, Str
from middlewared.service import CallError, Service


class PoolDatasetService(Service):

    class Config:
        namespace = "pool.dataset"

    @accepts(Str("dataset"), Bool("raise", default=True))
    @returns(Str(null=True))
    async def mountpoint(self, dataset, raise_):
        """
        Returns mountpoint for specific mounted dataset. If it is not mounted and `raise` is `true` (default), an
        error is raised. `null` is returned otherwise.
        """
        if mount_info := await self.middleware.call("filesystem.mount_info", [["mount_source", "=", dataset]]):
            return mount_info[0]["mountpoint"]

        if raise_:
            raise CallError(f"Dataset {dataset!r} is not mounted")
