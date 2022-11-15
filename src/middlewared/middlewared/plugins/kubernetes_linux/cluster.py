from middlewared.schema import accepts, Str
from middlewared.service import CallError, Service

from .k8s_new import apply_yaml_file


class KubernetesClusterService(Service):

    class Config:
        namespace = 'k8s.cluster'
        private = True

    @accepts(Str('file_path'))
    async def apply_yaml_file(self, file_path):
        cp = await apply_yaml_file(file_path)
        if cp.returncode:
            raise CallError(f'Failed to apply kubernetes yaml {file_path!r} file: {cp.stderr.decode()}')
