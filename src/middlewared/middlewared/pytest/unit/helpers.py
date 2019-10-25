import functools

from middlewared.utils import LoadPluginsMixin


def load_compound_service(name):
    lpm = LoadPluginsMixin()
    lpm._load_plugins()
    service = lpm.get_service(name)
    return functools.partial(_compound_service_wrapper, service)


def _compound_service_wrapper(service, fake_middleware):
    service.middleware = fake_middleware
    for part in service.parts:
        part.middleware = fake_middleware
    return service
