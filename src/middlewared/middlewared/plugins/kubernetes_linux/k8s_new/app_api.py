from .client import K8sClientBase
from .exceptions import ApiException
from .utils import UPDATE_HEADERS


class AppApi(K8sClientBase):

    NAMESPACE = '/apis/apps/v1/namespaces'

