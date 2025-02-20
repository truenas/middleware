from threading import Event

from middlewared.test.integration.assets.filesystem import mkfile
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils.client import client
from middlewared.test.integration.utils.call import call
from middlewared.test.integration.utils.ssh import ssh

from auto_config import pool_name

INS1_NAME = 'debian'
INS1_OS = 'Debian'
INS1_IMAGE = 'debian/trixie'

INS2_NAME = 'void'
INS2_OS = 'Void Linux'
INS2_IMAGE = 'voidlinux/musl'

INS3_NAME = 'ubuntu'
INS3_OS = 'Ubuntu'
INS3_IMAGE = 'ubuntu/oracular/default'


def clean():
    call('virt.global.update', {'pool': None}, job=True)
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
        call('virt.instance.create', {'name': INS1_NAME, 'image': INS1_IMAGE, 'instance_type': 'VM'}, job=True)

        call('virt.instance.create', {'name': INS2_NAME, 'image': INS2_IMAGE}, job=True)
        ssh(f'incus exec {INS2_NAME} cat /etc/os-release | grep "{INS2_OS}"')

        nics = list(call('virt.device.nic_choices', 'MACVLAN').keys())
        assert len(nics) > 0

        call('virt.instance.create', {
            'name': INS3_NAME,
            'image': INS3_IMAGE,
            'devices': [
                {'dev_type': 'TPM', 'path': '/dev/tpm0', 'pathrm': '/dev/tmprm0'},
                {'dev_type': 'PROXY', 'source_proto': 'TCP', 'source_port': 60123, 'dest_proto': 'TCP', 'dest_port': 2000},
                {'dev_type': 'NIC', 'name': 'eth1', 'nic_type': 'MACVLAN', 'parent': nics[0]},
            ],
        }, job=True)
        ssh(f'incus exec {INS3_NAME} cat /etc/os-release | grep "{INS3_OS}"')

        devices = call('virt.instance.device_list', INS3_NAME)
        assert any(i for i in devices if i['name'] == 'tpm0'), devices
        assert any(i for i in devices if i['name'] == 'proxy0'), devices
        assert any(i for i in devices if i['name'] == 'eth1'), devices

        assert wait_agent.wait(timeout=60)
        ssh(f'incus exec {INS1_NAME} cat /etc/os-release | grep "{INS1_OS}"')


def test_virt_instance_update():
    call('virt.instance.update', INS2_NAME, {'cpu': '1', 'memory': 500 * 1024 * 1024, 'environment': {'FOO': 'BAR'}}, job=True)
    ssh(f'incus exec {INS2_NAME} grep MemTotal: /proc/meminfo|grep 512000')
    # Checking CPUs seems to cause a racing condition (perhaps CPU currently in use in the container?)
    # rv = ssh('incus exec void cat /proc/cpuinfo |grep processor|wc -l')
    # assert rv.strip() == '1'
    rv = ssh(f'incus exec {INS2_NAME} env | grep ^FOO=')
    assert rv.strip() == 'FOO=BAR'

    call('virt.instance.update', INS2_NAME, {'cpu': None, 'memory': None, 'environment': {}}, job=True)

    rv = ssh(f'incus exec {INS2_NAME} env | grep ^FOO= || true')
    assert rv.strip() == ''


def test_virt_instance_stop():
    wait_status_event = Event()

    def wait_status(event_type, **kwargs):
        if kwargs['collection'] == 'virt.instance.query' and kwargs['id'] == INS2_NAME:
            fields = kwargs.get('fields')
            if fields and fields.get('status') == 'STOPPED':
                wait_status_event.set()

    with client() as c:
        c.subscribe('virt.instance.query', wait_status, sync=True)

        # Stop only one of them so the others are stopped during delete
        assert ssh(f'incus list {INS2_NAME} -f json| jq ".[].status"').strip() == '"Running"'
        instance = c.call('virt.instance.query', [['id', '=', INS2_NAME]], {'get': True})
        assert instance['status'] == 'RUNNING'
        call('virt.instance.stop', INS2_NAME, {'force': True}, job=True)
        instance = c.call('virt.instance.query', [['id', '=', INS2_NAME]], {'get': True})
        assert instance['status'] == 'STOPPED'
        assert wait_status_event.wait(timeout=1)
        assert ssh(f'incus list {INS2_NAME} -f json| jq ".[].status"').strip() == '"Stopped"'


def test_virt_instance_restart():
    # Stop only one of them so the others are stopped during delete
    assert ssh(f'incus list {INS3_NAME} -f json| jq ".[].status"').strip() == '"Running"'
    instance = call('virt.instance.query', [['id', '=', INS3_NAME]], {'get': True})
    assert instance['status'] == 'RUNNING'
    call('virt.instance.restart', INS3_NAME, {'force': True}, job=True)
    instance = call('virt.instance.query', [['id', '=', INS3_NAME]], {'get': True})
    assert instance['status'] == 'RUNNING'
    assert ssh(f'incus list {INS3_NAME} -f json| jq ".[].status"').strip() == '"Running"'


def test_virt_instance_device_add():
    assert ssh(f'incus list {INS1_NAME} -f json| jq ".[].status"').strip() == '"Running"'
    call('virt.instance.stop', INS1_NAME, {'force': True}, job=True)

    assert call('virt.instance.device_add', INS1_NAME, {
        'name': 'tpm',
        'dev_type': 'TPM',
    }) is True

    assert call('virt.instance.device_add', INS3_NAME, {
        'name': 'proxy',
        'dev_type': 'PROXY',
        'source_proto': 'TCP',
        'source_port': 8005,
        'dest_proto': 'TCP',
        'dest_port': 80,
    }) is True

    # TODO: adding to a VM causes start to hang at the moment (zombie process)
    # call('virt.instance.device_add', 'debian', {
    #     'name': 'disk1',
    #     'dev_type': 'DISK',
    #     'source': f'/mnt/{pool_name}',
    #     'destination': '/host',
    # })

    devices = call('virt.instance.device_list', INS1_NAME)
    assert any(i for i in devices if i['name'] == 'tpm'), devices
    devices = call('virt.instance.device_list', INS3_NAME)
    assert any(i for i in devices if i['name'] == 'proxy'), devices
    # assert 'disk1' in devices, devices

    wait_agent = Event()

    def wait_debian(*args, **kwargs):
        wait_agent.set()

    with client() as c:
        c.subscribe('virt.instance.agent_running', wait_debian, sync=True)
        call('virt.instance.start', INS1_NAME, job=True)
        assert wait_agent.wait(timeout=30)

    ssh('incus exec debian ls /dev/tpm0')
    # ssh('incus exec debian ls /host')

    with dataset('virtshare') as ds:
        call('virt.instance.device_add', INS3_NAME, {
            'name': 'disk1',
            'dev_type': 'DISK',
            'source': f'/mnt/{ds}',
            'destination': '/host',
        })
        devices = call('virt.instance.device_list', INS3_NAME)
        assert any(i for i in devices if i['name'] == 'disk1'), devices
        with mkfile(f'/mnt/{ds}/testfile'):
            ssh(f'incus exec {INS3_NAME} ls /host/testfile')
        assert call('virt.instance.device_delete', INS3_NAME, 'disk1') is True

    with dataset('virtshare', {'type': 'VOLUME', 'volsize': 200 * 1024 * 1024, 'sparse': True}) as ds:
        ssh(f'mkfs.ext3 /dev/zvol/{ds}')
        call('virt.instance.device_add', INS3_NAME, {
            'name': 'disk2',
            'dev_type': 'DISK',
            'source': f'/dev/zvol/{ds}',
            'destination': '/zvol',
        })
        devices = call('virt.instance.device_list', INS3_NAME)
        assert any(i for i in devices if i['name'] == 'disk2'), devices
        ssh(f'incus exec {INS3_NAME} mount|grep "on /zvol"|grep ext3')
        assert call('virt.instance.device_delete', INS3_NAME, 'disk2') is True


def test_virt_instance_device_update():
    assert call('virt.instance.device_update', INS3_NAME, {
        'name': 'proxy',
        'dev_type': 'PROXY',
        'source_proto': 'TCP',
        'source_port': 8005,
        'dest_proto': 'TCP',
        'dest_port': 81,
    }) is True


def test_virt_instance_proxy():
    ssh(f'incus exec -T {INS3_NAME} -- bash -c "nohup nc -l 0.0.0.0 81 > /tmp/nc 2>&1 &"')
    ssh('echo "foo" | nc -w 1 localhost 8005 || true')
    rv = ssh(f'incus exec {INS3_NAME} -- cat /tmp/nc')

    assert rv.strip() == 'foo'


def test_virt_instance_shell():
    assert call('virt.instance.get_shell', INS3_NAME) == '/bin/bash'


def test_virt_instance_device_delete():
    call('virt.instance.stop', INS1_NAME, {'force': True}, job=True)
    assert call('virt.instance.device_delete', INS1_NAME, 'tpm') is True
    devices = call('virt.instance.device_list', INS1_NAME)
    assert not any(i for i in devices if i['name'] == 'tpm'), devices


def test_virt_instance_delete():
    call('virt.instance.delete', INS2_NAME, job=True)
    ssh(f'incus config show {INS2_NAME} 2>&1 | grep "not found"')

    call('virt.instance.delete', INS3_NAME, job=True)
    ssh(f'incus config show {INS3_NAME} 2>&1 | grep "not found"')

    call('virt.instance.delete', INS1_NAME, job=True)
    ssh(f'incus config show {INS1_NAME} 2>&1 | grep "not found"')

    assert len(call('virt.instance.query')) == 0
