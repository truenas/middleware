from .client import K8sClientBase


class CoreAPI(K8sClientBase):

    NAMESPACE = '/api/v1/namespaces'

    @classmethod
    async def query(cls):
        pass
