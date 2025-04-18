import contextlib

from middlewared.service_exception import MatchNotFound
from middlewared.test.integration.utils import call

NVME_DEFAULT_TCP_PORT = 4420

__all__ = [
    'nvmet_host',
    'nvmet_namespace',
    'nvmet_port',
    'nvmet_subsys',
    'nvmet_host_subsys',
    'nvmet_port_subsys',
    'nvmet_xport_referral',
    'nvmet_ana',
    'NVME_DEFAULT_TCP_PORT'
]


def _exists(item: str, id_: int) -> bool:
    try:
        call(f'nvmet.{item}.query',
             [['id', '=', id_]],
             {'get': True})
    except MatchNotFound:
        return False
    return True


@contextlib.contextmanager
def nvmet_host(hostnqn, **kwargs):
    delete_exist_precheck = kwargs.pop('delete_exist_precheck', False)
    host = call('nvmet.host.create', {'hostnqn': hostnqn,
                                      **kwargs})
    try:
        yield host
    finally:
        if not delete_exist_precheck or _exists('host', host['id']):
            call('nvmet.host.delete', host['id'])


@contextlib.contextmanager
def nvmet_namespace(subsys_id, device_path, device_type='ZVOL', **kwargs):
    delete_exist_precheck = kwargs.pop('delete_exist_precheck', False)
    delete_options = kwargs.pop('delete_options', {})
    namespace = call('nvmet.namespace.create', {'subsys_id': subsys_id,
                                                'device_path': device_path,
                                                'device_type': device_type,
                                                **kwargs})
    try:
        yield namespace
    finally:
        if not delete_exist_precheck or _exists('namespace', namespace['id']):
            call('nvmet.namespace.delete', namespace['id'], delete_options)


@contextlib.contextmanager
def nvmet_port(traddr, trsvcid=NVME_DEFAULT_TCP_PORT, trtype='TCP', **kwargs):
    delete_exist_precheck = kwargs.pop('delete_exist_precheck', False)
    port = call('nvmet.port.create', {'addr_traddr': traddr,
                                      'addr_trsvcid': trsvcid,
                                      'addr_trtype': trtype,
                                      **kwargs})

    try:
        yield port
    finally:
        if not delete_exist_precheck or _exists('port', port['id']):
            call('nvmet.port.delete', port['id'])


@contextlib.contextmanager
def nvmet_subsys(name, **kwargs):
    delete_exist_precheck = kwargs.pop('delete_exist_precheck', False)
    subsys = call('nvmet.subsys.create', {'name': name,
                                          **kwargs})
    try:
        yield subsys
    finally:
        if not delete_exist_precheck or _exists('subsys', subsys['id']):
            call('nvmet.subsys.delete', subsys['id'])


@contextlib.contextmanager
def nvmet_host_subsys(host_id, subsys_id, **kwargs):
    delete_exist_precheck = kwargs.pop('delete_exist_precheck', False)
    host_subsys = call('nvmet.host_subsys.create', {'host_id': host_id,
                                                    'subsys_id': subsys_id,
                                                    **kwargs})
    try:
        yield host_subsys
    finally:
        if not delete_exist_precheck or _exists('host_subsys', host_subsys['id']):
            call('nvmet.host_subsys.delete', host_subsys['id'])


@contextlib.contextmanager
def nvmet_port_subsys(subsys_id: int, port_id: int, **kwargs):
    delete_exist_precheck = kwargs.pop('delete_exist_precheck', False)
    port_subsys = call('nvmet.port_subsys.create', {'subsys_id': subsys_id,
                                                    'port_id': port_id,
                                                    **kwargs})
    try:
        yield port_subsys
    finally:
        if not delete_exist_precheck or _exists('port_subsys', port_subsys['id']):
            call('nvmet.port_subsys.delete', port_subsys['id'])


@contextlib.contextmanager
def _global_config_bool(variable: str, state: bool):
    orig = call('nvmet.global.config')[variable]
    if orig != state:
        call('nvmet.global.update', {variable: state})
    try:
        yield
    finally:
        if orig != state:
            call('nvmet.global.update', {variable: orig})


@contextlib.contextmanager
def nvmet_xport_referral(state: bool):
    with _global_config_bool('xport_referral', state):
        yield


@contextlib.contextmanager
def nvmet_ana(state: bool):
    with _global_config_bool('ana', state):
        yield
