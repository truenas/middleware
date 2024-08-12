from middlewared.test.integration.utils import call


def test_01_enable_services():
    for svc in filter(lambda x: not x['enable'], call('service.query')):
        call('service.update', svc['id'], {'enable': True})


def test_02_disable_services():
    for svc in filter(lambda x: x['enable'], call('service.query')):
        call('service.update', svc['id'], {'enable': False})
