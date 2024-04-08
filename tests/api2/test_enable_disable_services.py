from middlewared.test.integration.utils import call

def enable_services():
    for svc in filter(lambda x: not x['enable'], call('service.query'):
        call('service.update', svc['id'], {'enable': True})


def disable_services():
    for svc in filter(lambda x: x['enable'], call('service.query'):
        call('service.update', svc['id'], {'enable': True})
