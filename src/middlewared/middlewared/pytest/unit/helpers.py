import functools
import sys
from unittest.mock import Mock

from middlewared.utils import osc
from middlewared.utils.plugins import LoadPluginsMixin


# freenasOS
if osc.IS_FREEBSD:
    if '/usr/local/lib' not in sys.path:
        sys.path.append('/usr/local/lib')


def load_compound_service(name):
    lpm = LoadPluginsMixin()
    lpm.event_register = Mock()
    lpm._load_plugins()
    service = lpm.get_service(name)
    return functools.partial(_compound_service_wrapper, service)


def _compound_service_wrapper(service, fake_middleware):
    service.middleware = fake_middleware
    for part in service.parts:
        part.middleware = fake_middleware
    return service
