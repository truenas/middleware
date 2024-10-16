from threading import Event

from middlewared.test.integration.assets.filesystem import mkfile
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils.client import client
from middlewared.test.integration.utils.call import call
from middlewared.test.integration.utils.ssh import ssh

from auto_config import pool_name


def clean():
    call('virt.global.update', {'pool': ''}, job=True)
    ssh(f'zfs destroy -r {pool_name}/.ix-virt || true')
    call('virt.global.update', {'pool': 'tank'}, job=True)


def test_virt_instance_create():
    clean()

    wait_agent = Event()

    def wait_debian(*args, **kwargs):
        wait_agent.set()

    with client() as c:
        c.subscribe('virt.instance.agent_running', wait_debian, sync=True)

        # Create first so there is time for the agent to start
        call('virt.instance.create', {'name': 'debian', 'image': 'debian/trixie', 'instance_type': 'VM'}, job=True)

        call('virt.instance.create', {'name': 'void', 'image': 'voidlinux/musl'}, job=True)
        ssh('incus exec void cat /etc/os-release | grep "Void Linux"')

        call('virt.instance.create', {
            'name': 'arch',
            'image': 'archlinux/current/default',
            'devices': [
                {'name': 'tpm', 'dev_type': 'TPM', 'path': '/dev/tpm0', 'pathrm': '/dev/tmprm0'},
            ],
        }, job=True)
        ssh('incus exec arch cat /etc/os-release | grep "Arch Linux"')

        devices = call('virt.instance.device_list', 'arch')
        assert any(i for i in devices if i['name'] == 'tpm'), devices

        assert wait_agent.wait(timeout=30)
        ssh('incus exec debian cat /etc/os-release | grep "Debian"')


def test_virt_instance_update():
    call('virt.instance.update', 'void', {'cpu': '1', 'memory': 500 * 1024 * 1024, 'environment': {'FOO': 'BAR'}}, job=True)
    ssh('incus exec void grep MemTotal: /proc/meminfo|grep 512000')
    # Checking CPUs seems to cause a racing condition (perhaps CPU currently in use in the container?)
    # rv = ssh('incus exec void cat /proc/cpuinfo |grep processor|wc -l')
    # assert rv.strip() == '1'
    rv = ssh('incus exec void env | grep ^FOO=')
    assert rv.strip() == 'FOO=BAR'


def test_virt_instance_stop():
    # Stop only one of them so the others are stopped during delete
    assert ssh('incus list void -f json| jq ".[].status"').strip() == '"Running"'
    instance = call('virt.instance.query', [['id', '=', 'void']], {'get': True})
    assert instance['status'] == 'RUNNING'
    call('virt.instance.stop', 'void', {'force': True}, job=True)
    instance = call('virt.instance.query', [['id', '=', 'void']], {'get': True})
    assert instance['status'] == 'STOPPED'
    assert ssh('incus list void -f json| jq ".[].status"').strip() == '"Stopped"'


def test_virt_instance_device_add():
    assert ssh('incus list debian -f json| jq ".[].status"').strip() == '"Running"'
    call('virt.instance.stop', 'debian', {'force': True}, job=True)

    call('virt.instance.device_add', 'debian', {
        'name': 'tpm',
        'dev_type': 'TPM',
    })

    call('virt.instance.device_add', 'arch', {
        'name': 'proxy',
        'dev_type': 'PROXY',
        'source_proto': 'TCP',
        'source_port': 8005,
        'dest_proto': 'TCP',
        'dest_port': 80,
    })

    # TODO: adding to a VM causes start to hang at the moment (zombie process)
    # call('virt.instance.device_add', 'debian', {
    #     'name': 'disk1',
    #     'dev_type': 'DISK',
    #     'source': f'/mnt/{pool_name}',
    #     'destination': '/host',
    # })

    devices = call('virt.instance.device_list', 'debian')
    assert any(i for i in devices if i['name'] == 'tpm'), devices
    devices = call('virt.instance.device_list', 'arch')
    assert any(i for i in devices if i['name'] == 'proxy'), devices
    # assert 'disk1' in devices, devices

    wait_agent = Event()

    def wait_debian(*args, **kwargs):
        wait_agent.set()

    with client() as c:
        c.subscribe('virt.instance.agent_running', wait_debian, sync=True)
        call('virt.instance.start', 'debian', job=True)
        assert wait_agent.wait(timeout=30)

    ssh('incus exec debian ls /dev/tpm0')
    # ssh('incus exec debian ls /host')

    with dataset('virtshare') as ds:
        call('virt.instance.device_add', 'arch', {
            'name': 'disk1',
            'dev_type': 'DISK',
            'source': f'/mnt/{ds}',
            'destination': '/host',
        })
        devices = call('virt.instance.device_list', 'arch')
        assert any(i for i in devices if i['name'] == 'disk1'), devices
        with mkfile(f'/mnt/{ds}/testfile'):
            ssh('incus exec arch ls /host/testfile')
        call('virt.instance.device_delete', 'arch', 'disk1')


def test_virt_instance_proxy():
    ssh('incus exec arch -- pacman -S --noconfirm openbsd-netcat')
    ssh('incus exec -T arch -- bash -c "nohup nc -l 0.0.0.0 80 > /tmp/nc 2>&1 &"')
    ssh('echo "foo" | nc -w 1 localhost 8005 || true')
    rv = ssh('incus exec arch -- cat /tmp/nc')

    assert rv.strip() == 'foo'


def test_virt_instance_device_delete():
    call('virt.instance.stop', 'debian', {'force': True}, job=True)
    call('virt.instance.device_delete', 'debian', 'tpm')
    devices = call('virt.instance.device_list', 'debian')
    assert not any(i for i in devices if i['name'] == 'tpm'), devices


def test_virt_instance_delete():
    call('virt.instance.delete', 'void', job=True)
    ssh('incus config show void 2>&1 | grep "not found"')

    call('virt.instance.delete', 'arch', job=True)
    ssh('incus config show arch 2>&1 | grep "not found"')

    call('virt.instance.delete', 'debian', job=True)
    ssh('incus config show debian 2>&1 | grep "not found"')

    assert len(call('virt.instance.query')) == 0
