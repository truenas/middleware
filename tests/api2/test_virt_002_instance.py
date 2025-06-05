import pytest

from threading import Event

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.filesystem import mkfile
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.virt import (
    userns_user,
    userns_group,
    virt,
    virt_device,
    virt_instance,
)
from middlewared.test.integration.utils import call, client, ssh, pool

INS2_NAME = 'void'
INS2_OS = 'Void Linux'
INS2_IMAGE = 'voidlinux/musl'

INS3_NAME = 'ubuntu'
INS3_OS = 'Ubuntu'
INS3_IMAGE = 'ubuntu/oracular/default'


@pytest.fixture(scope='module')
def virt_setup():
    # ensure that any stale config from other tests is nuked
    call('virt.global.update', {'pool': None}, job=True)
    ssh(f'zfs destroy -r {pool}/.ix-virt || true')

    with virt():
        yield


def check_idmap_entry(instance_name, entry):
    raw = call('virt.instance.get_instance', instance_name, {'extra': {'raw': True}})['raw']

    assert 'raw.idmap' in raw['config']
    return entry in raw['config']['raw.idmap']


@pytest.fixture(scope='module')
def virt_instances(virt_setup):
    # Create first so there is time for the agent to start
    with virt_instance(INS2_NAME, INS2_IMAGE) as v2:
        nics = list(call('virt.device.nic_choices', 'MACVLAN').keys())
        assert len(nics) > 0
        with virt_instance(INS3_NAME, INS3_IMAGE, devices=[
            {
                'dev_type': 'TPM',
                'path': '/dev/tpm0',
                'pathrm': '/dev/tmprm0'
            },
            {
                'dev_type': 'PROXY',
                'source_proto': 'TCP',
                'source_port': 60123,
                'dest_proto': 'TCP',
                'dest_port': 2000
            },
            {
                'dev_type': 'NIC',
                'name': 'eth1',
                'nic_type': 'MACVLAN',
                'parent': nics[0]
            },
        ]) as v3:
            yield v2, v3


def test_virt_instance_create(virt_instances):
    for name, os_rel in (
        (INS2_NAME, INS2_OS),
        (INS3_NAME, INS3_OS),
    ):
        ssh(f'incus exec {name} grep "{os_rel}" /etc/os-release')

    devices = call('virt.instance.device_list', INS3_NAME)
    assert any(i for i in devices if i['name'] == 'tpm0'), devices
    assert any(i for i in devices if i['name'] == 'proxy0'), devices
    assert any(i for i in devices if i['name'] == 'eth1'), devices


def test_virt_instance_update(virt_instances):
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


def test_virt_instance_stop(virt_instances):
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


def test_virt_instance_restart(virt_instances):
    # Stop only one of them so the others are stopped during delete
    assert ssh(f'incus list {INS3_NAME} -f json| jq ".[].status"').strip() == '"Running"'
    instance = call('virt.instance.query', [['id', '=', INS3_NAME]], {'get': True})
    assert instance['status'] == 'RUNNING'
    call('virt.instance.restart', INS3_NAME, {'force': True}, job=True)
    instance = call('virt.instance.query', [['id', '=', INS3_NAME]], {'get': True})
    assert instance['status'] == 'RUNNING'
    assert ssh(f'incus list {INS3_NAME} -f json| jq ".[].status"').strip() == '"Running"'


def test_virt_instance_device_add(virt_instances):
    assert call('virt.instance.device_add', INS3_NAME, {
        'name': 'proxy',
        'dev_type': 'PROXY',
        'source_proto': 'TCP',
        'source_port': 8005,
        'dest_proto': 'TCP',
        'dest_port': 80,
    }) is True

    devices = call('virt.instance.device_list', INS3_NAME)
    assert any(i for i in devices if i['name'] == 'proxy'), devices

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


def test_virt_instance_device_update(virt_instances):
    assert call('virt.instance.device_update', INS3_NAME, {
        'name': 'proxy',
        'dev_type': 'PROXY',
        'source_proto': 'TCP',
        'source_port': 8005,
        'dest_proto': 'TCP',
        'dest_port': 81,
    }) is True


def test_virt_instance_proxy(virt_instances):
    ssh(f'incus exec -T {INS3_NAME} -- bash -c "nohup nc -l 0.0.0.0 81 > /tmp/nc 2>&1 &"')
    ssh('echo "foo" | nc -w 1 localhost 8005 || true')
    rv = ssh(f'incus exec {INS3_NAME} -- cat /tmp/nc')

    assert rv.strip() == 'foo'


def test_virt_instance_shell(virt_instances):
    assert call('virt.instance.get_shell', INS3_NAME) == '/bin/bash'


def test_virt_instance_idmap(virt_instances):
    with virt_instance('tmpinstance') as instance:
        uid = None
        gid = None
        assert 'raw.idmap' in instance['raw']['config']
        # check that apps user / group are present
        assert check_idmap_entry(instance['name'], f'uid 568 568')
        assert check_idmap_entry(instance['name'], f'gid 568 568')

        with userns_user('bob') as u:
            # check user DIRECT map
            uid = u['uid']
            assert u['userns_idmap'] == 'DIRECT'
            call('virt.instance.restart', instance['name'], {'force': True}, job=True)
            assert check_idmap_entry(instance['name'], f'uid {uid} {uid}')

            # check custom user map
            call('user.update', u['id'], {'userns_idmap': 8675309})

            # restart to update idmap
            call('virt.instance.restart', instance['name'], {'force': True}, job=True)
            assert check_idmap_entry(instance['name'], f'uid {uid} 8675309')
            assert not check_idmap_entry(instance['name'], f'uid {uid} {uid}')

        call('virt.instance.restart', instance['name'], {'force': True}, job=True)
        assert not check_idmap_entry(instance['name'], f'uid {uid} 8675309')

        with userns_group('bob_group') as g:
            gid = g['gid']
            assert g['userns_idmap'] == 'DIRECT'
            call('virt.instance.restart', instance['name'], {'force': True}, job=True)

            assert check_idmap_entry(instance['name'], f'gid {gid} {gid}')
            # check custom user map
            call('group.update', g['id'], {'userns_idmap': 8675309})

            # restart to update idmap
            call('virt.instance.restart', instance['name'], {'force': True}, job=True)
            assert not check_idmap_entry(instance['name'], f'gid {gid} {gid}')
            assert check_idmap_entry(instance['name'], f'gid {gid} 8675309')

        call('virt.instance.restart', instance['name'], {'force': True}, job=True)
        assert not check_idmap_entry(instance['name'], f'gid {gid} 8675309')


def test_virt_instance_device_validation(virt_setup):
    with dataset('tmpdataset') as ds:
        with virt_instance('tmpinstance') as i:
            ssh(f'mkdir /mnt/{ds}/testdir')

            # check path is dataset mountpoint
            with pytest.raises(ValidationErrors, match='Source must be a dataset mountpoint.'):
                with virt_device(i['name'], 'testdisk', {
                    'dev_type': 'DISK',
                    'source': f'/mnt/{ds}/testdir',
                    'destination': '/nfs4acl',
                }):
                    pass

            ssh(f'mkdir /mnt/testdir')

            # check path outside known pools
            with pytest.raises(ValidationErrors, match='The path must reside within a pool mount point'):
                with virt_device(i['name'], 'testdisk', {
                    'dev_type': 'DISK',
                    'source': f'/mnt/testdir',
                    'destination': '/nfs4acl',
                }):
                    pass
