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

        call('virt.instance.create', {
            'name': INS3_NAME,
            'image': INS3_IMAGE,
            'devices': [
                {'name': 'tpm', 'dev_type': 'TPM', 'path': '/dev/tpm0', 'pathrm': '/dev/tmprm0'},
            ],
        }, job=True)
        ssh(f'incus exec {INS3_NAME} cat /etc/os-release | grep "{INS3_OS}"')

        devices = call('virt.instance.device_list', INS3_NAME)
        assert any(i for i in devices if i['name'] == 'tpm'), devices

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


def test_virt_instance_stop():
    # Stop only one of them so the others are stopped during delete
    assert ssh(f'incus list {INS2_NAME} -f json| jq ".[].status"').strip() == '"Running"'
    instance = call('virt.instance.query', [['id', '=', INS2_NAME]], {'get': True})
    assert instance['status'] == 'RUNNING'
    call('virt.instance.stop', INS2_NAME, {'force': True}, job=True)
    instance = call('virt.instance.query', [['id', '=', INS2_NAME]], {'get': True})
    assert instance['status'] == 'STOPPED'
    assert ssh(f'incus list {INS2_NAME} -f json| jq ".[].status"').strip() == '"Stopped"'


def test_virt_instance_device_add():
    assert ssh(f'incus list {INS1_NAME} -f json| jq ".[].status"').strip() == '"Running"'
    call('virt.instance.stop', INS1_NAME, {'force': True}, job=True)

    call('virt.instance.device_add', INS1_NAME, {
        'name': 'tpm',
        'dev_type': 'TPM',
    })

    call('virt.instance.device_add', INS3_NAME, {
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
        call('virt.instance.device_delete', INS3_NAME, 'disk1')


def test_virt_instance_proxy():
    ssh(f'incus exec -T {INS3_NAME} -- bash -c "nohup nc -l 0.0.0.0 80 > /tmp/nc 2>&1 &"')
    ssh('echo "foo" | nc -w 1 localhost 8005 || true')
    rv = ssh(f'incus exec {INS3_NAME} -- cat /tmp/nc')

    assert rv.strip() == 'foo'


def test_virt_instance_device_delete():
    call('virt.instance.stop', INS1_NAME, {'force': True}, job=True)
    call('virt.instance.device_delete', INS1_NAME, 'tpm')
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
