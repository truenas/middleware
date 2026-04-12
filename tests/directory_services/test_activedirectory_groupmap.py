import pytest

from middlewared.test.integration.assets.directory_service import directoryservice
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.system import reset_systemd_svcs

GROUP_MAPPING_TDB = '/var/lib/truenas-samba/group_mapping.tdb'

# Well-known builtin alias SIDs
BUILTIN_ADMINISTRATORS = 'S-1-5-32-544'
BUILTIN_USERS = 'S-1-5-32-545'
BUILTIN_GUESTS = 'S-1-5-32-546'

# Well-known domain RIDs
DOMAIN_ADMINS_RID = 512
DOMAIN_USERS_RID = 513
DOMAIN_GUESTS_RID = 514


def test_ad_foreign_group_recovery():
    """
    Verify that after deleting group_mapping.tdb, synchronize_group_mappings
    restores foreign group memberships for both local and AD domain SIDs.

    Domain Admins (RID 512) must be a member of BUILTIN\\Administrators (S-1-5-32-544).
    Domain Users  (RID 513) must be a member of BUILTIN\\Users (S-1-5-32-545).
    Domain Guests (RID 514) must be a member of BUILTIN\\Guests (S-1-5-32-546).
    """
    reset_systemd_svcs('winbind')

    with directoryservice('ACTIVEDIRECTORY') as ad:
        short_name = ad['domain_info']['domain_controller']['pre-win2k_domain']
        domain_sid = call('directoryservices.secrets.domain_sid', short_name)

        # Verify domain_sid looks reasonable
        assert domain_sid.startswith('S-1-5-21-')

        # Delete group_mapping.tdb to simulate data loss
        ssh(f'rm -f {GROUP_MAPPING_TDB}')

        # Memberships should be gone now
        assert call('smb.groupmap_listmem', BUILTIN_ADMINISTRATORS) == []

        # Rebuild group mappings from scratch
        call('smb.synchronize_group_mappings', job=True)

        # Verify local domain foreign memberships were restored
        admin_members = call('smb.groupmap_listmem', BUILTIN_ADMINISTRATORS)
        user_members = call('smb.groupmap_listmem', BUILTIN_USERS)
        guest_members = call('smb.groupmap_listmem', BUILTIN_GUESTS)

        # Local builtin_administrators (RID 512) should be member of S-1-5-32-544
        localsid = call('smb.groupmap_list')['localsid']
        assert f'{localsid}-{DOMAIN_ADMINS_RID}' in admin_members
        assert f'{localsid}-{DOMAIN_GUESTS_RID}' in guest_members

        # AD domain SIDs should also be present as foreign members
        assert f'{domain_sid}-{DOMAIN_ADMINS_RID}' in admin_members, \
            f'Domain Admins SID not in BUILTIN\\Administrators members: {admin_members}'
        assert f'{domain_sid}-{DOMAIN_USERS_RID}' in user_members, \
            f'Domain Users SID not in BUILTIN\\Users members: {user_members}'
        assert f'{domain_sid}-{DOMAIN_GUESTS_RID}' in guest_members, \
            f'Domain Guests SID not in BUILTIN\\Guests members: {guest_members}'
