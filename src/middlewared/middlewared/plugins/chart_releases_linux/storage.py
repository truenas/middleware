from middlewared.plugins.cluster_linux.utils import FuseConfig
from middlewared.service import CallError, private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def validate_cluster_path(self, path):
        # Will return None if no error is found, otherwise an error string will be returned
        if not path.startswith(f'{FuseConfig.FUSE_PATH_BASE.value}/'):
            return f'Path must start with {FuseConfig.FUSE_PATH_BASE.value!r}'

        # We will try to resolve this path now and if it resolves, we are good - otherwise the specified error
        # will be propagated back to docker where in its CSI it will raise appropriate exception
        try:
            await self.middleware.call(
                'filesystem.resolve_cluster_path', path.replace(
                    f'{FuseConfig.FUSE_PATH_BASE.value}/', FuseConfig.FUSE_PATH_SUBST.value
                )
            )
        except CallError as e:
            return str(e)
