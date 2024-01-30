#!/usr/bin/env python3

import os
import pytest
import sys

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ha
from middlewared.test.integration.utils import call, ssh


MD_DEVICE_NAME = 'mddevicetest'
MD_DEVICE_MIRROR_LENGTH = 2
pytestmark = pytest.mark.disk

if not ha:
    # HA vms don't have enough disks for this so skip
    def create_md_device(md_mirror_name, disks):
        if len(disks) < MD_DEVICE_MIRROR_LENGTH:
            pytest.skip(f'Skipping because at least {MD_DEVICE_MIRROR_LENGTH} unused disks are required')

        for disk in disks[:MD_DEVICE_MIRROR_LENGTH]:
            call('disk.wipe', disk['name'], 'QUICK', job=True)

        md_device_disks = [f'/dev/{disks[i]["name"]}' for i in range(MD_DEVICE_MIRROR_LENGTH)]
        ssh(
            f'mdadm --create /dev/md/{md_mirror_name} {" ".join(md_device_disks)} --level=1 '
            f'--raid-devices={MD_DEVICE_MIRROR_LENGTH} --meta=1.2 --force',
        )


    def destroy_md_device(mirror_name):
        md_device = call('disk.get_md_devices', [['name', '=', mirror_name]], {'get': True})
        call('disk.stop_md_device', md_device['path'], False)
        call('disk.clean_superblocks_on_md_device', [p['name'] for p in md_device['providers']], False)


    def test_pool_creation_with_md_device_used_disks(request):
        disks = call('disk.get_unused')
        create_md_device(MD_DEVICE_NAME, disks)

        error = None
        try:
            pool = call('pool.create', {
                'name': 'testmd',
                'encryption': False,
                'allow_duplicate_serials': True,
                'topology': {
                    'data': [
                        {'type': 'STRIPE', 'disks': [disk['devname'] for disk in disks[:MD_DEVICE_MIRROR_LENGTH]]},
                    ],
                },
            }, job=True)
        except Exception as e:
            error = e
        else:
            call('pool.export', pool['id'], job=True)

        assert error is None, f'Unable to create pool on md device disks: {error!r}'


    def test_disk_unused_correctly_reports_user_configured_md_device(request):
        disks = call('disk.get_unused')
        try:
            create_md_device(MD_DEVICE_NAME, disks)
            to_check_disks = [disk['name'] for disk in disks[:MD_DEVICE_MIRROR_LENGTH]]
            for disk in call('disk.get_unused'):
                if disk['name'] in to_check_disks and disk['unsupported_md_devices'] == [MD_DEVICE_NAME]:
                    to_check_disks.remove(disk['name'])

            assert to_check_disks == [], f'{", ".join(to_check_disks)!r} disks not ' \
                                         f'correctly reported as being used by md devices'
        finally:
            destroy_md_device(MD_DEVICE_NAME)
