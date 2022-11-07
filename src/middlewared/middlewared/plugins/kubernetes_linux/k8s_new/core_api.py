from .client import K8sClientBase


class CoreAPI(K8sClientBase):

    NAMESPACE = '/api/v1/namespaces'

    async def query(self):
        return self.call(self.uri(), mode='get')
