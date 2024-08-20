import os
import pytest
import json

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh

SMB_NAME = 'groupmap_migrate'
RO_ADMINS = 'truenas_readonly_administrators'


@pytest.fixture(scope='module')
def do_setup():
    with dataset('groupmap-migrate', data={'share_type': 'SMB'}) as ds:
        with smb_share(os.path.join('/mnt', ds), SMB_NAME) as s:
            ro = call('group.query', [['group', '=', RO_ADMINS]], {'get': True})
            acl = call('sharing.smb.setacl', {
                'share_name': SMB_NAME,
                'share_acl': [{
                    'ae_who_id': {'id_type': 'GROUP', 'id': ro['gid']},
                    'ae_perm': 'READ',
                    'ae_type': 'ALLOWED'
                }]
            })
            yield {'dataset': ds, 'share': s, 'acl': acl, 'group': ro}


def test_groupmap_migrate(do_setup):
    assert do_setup['acl']['share_name'] == SMB_NAME
    assert do_setup['acl']['share_acl'][0]['ae_perm'] == 'READ'
    assert do_setup['acl']['share_acl'][0]['ae_who_sid'] == do_setup['group']['sid']

    # first delete existing groupmap
    ssh(f'net groupmap delete ntgroup={RO_ADMINS}')

    # Adding it back will force auto-allocation from low RID range
    ssh(f'net groupmap add ntgroup={RO_ADMINS} unixgroup={RO_ADMINS}')

    groupmap = json.loads(ssh('net groupmap list --json'))
    sid = None
    for entry in groupmap['groupmap']:
        if entry['gid'] != do_setup['group']['gid']:
            continue

        sid = entry['sid']

    # Make sure we have an actually different sid in the groupmap
    assert sid != do_setup['group']['sid']

    # first update ACL to have mapping to new sid
    call('smb.sharesec.setacl', {'share_name': SMB_NAME, 'share_acl': [{
        'ae_who_sid': sid,
        'ae_perm': 'READ',
        'ae_type': 'ALLOWED'
    }]})

    # make sure it's actually set
    new_acl = call('smb.sharesec.getacl', SMB_NAME)
    assert new_acl['share_acl'][0]['ae_who_sid'] == sid

    # We catch inconsistency when dumping groupmap and auto-migrate at that time
    call('smb.groupmap_list')

    new_acl = call('smb.sharesec.getacl', SMB_NAME)
    assert new_acl['share_acl'][0]['ae_who_sid'] == do_setup['group']['sid']
