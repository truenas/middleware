# Utilites related to SMB security descriptors
#
# These are primarily used for manipulating the SMB share ACL, which
# is stored in samba's share_info.tdb file as a packed security descriptor
# In principle, this code can also be used to decode SDDL strings and to
# parse security descriptors from remote servers.
#
# Tests are provided in pytest/unit/utils/test_security_descriptor.py

import enum
from typing import Any

from samba.ndr import ndr_pack, ndr_unpack
from samba.dcerpc import security


CUSTOM_ACCESS_MASK_STRING = "CUSTOM"


class SDDLAceType(enum.Enum):
    """ defined in MS-DTYP """
    ALLOWED = 'A'
    DENIED = 'D'


class SDDLAccessMaskStandard(enum.IntEnum):
    """ defined in source3/lib/util_sd.c """
    FULL = security.SEC_RIGHTS_DIR_ALL
    CHANGE = 0x1301ff  # DIR_READ | STD_DELETE | DELETE_CHILD | WRITE | TRAVERSE
    READ = security.SEC_RIGHTS_DIR_READ | security.SEC_RIGHTS_DIR_EXECUTE


def security_descriptor_from_bytes(sd_buf: bytes) -> security.descriptor:
    """
    method to convert bytes to security descriptor. This is particularly
    relevant for security descriptor we store in share config containing
    a backup copy of the share ACL.
    """
    return ndr_unpack(security.descriptor, sd_buf)


def security_descriptor_to_bytes(sd: security.descriptor) -> bytes:
    """
    method to convert security descriptor to bytes for insertion into
    share_info.tdb and SMB share configuration
    """
    return ndr_pack(sd)


def share_acl_to_sd_bytes(share_acl: list[dict[str, Any]]) -> bytes:
    """ Convert share_acl list to SDDL string and then to security descriptor bytes """
    sddl_str = 'D:'
    for ace in share_acl:
        if ace['ae_perm'] == CUSTOM_ACCESS_MASK_STRING:
            raise ValueError(
                'CUSTOM perm is not supported for writing an ACL. The '
                'presence of this value indicates that the share ACL was '
                'written outside of the TrueNAS API / UI and so should be '
                'adjusted to a supported value'
            )

        sddl_ace_type = SDDLAceType[ace['ae_type']].value
        sddl_access = hex(SDDLAccessMaskStandard[ace['ae_perm']].value)
        sddl_sid = ace['ae_who_sid']
        sddl_ace = f'({sddl_ace_type};;{sddl_access};;;{sddl_sid})'
        sddl_str += sddl_ace

    sd_obj = security.descriptor().from_sddl(sddl_str, security.dom_sid())
    if sd_obj.dacl is None:
        raise ValueError(f'{sddl_str}, malformed sddl string')

    return security_descriptor_to_bytes(sd_obj)


def sd_bytes_to_share_acl(sd_bytes: bytes) -> list[dict[str, str]]:
    """ Convert security descriptor bytes to share middleware SMB share ACL """
    if not sd_bytes:
        return []

    sd = security_descriptor_from_bytes(sd_bytes)
    share_acl = []

    for ace in sd.dacl.aces:
        dom_sid = str(ace.trustee)

        try:
            perm = SDDLAccessMaskStandard(ace.access_mask).name
        except ValueError:
            # See NAS-139535 -- non-standard access mask is set in share ACL
            # We'll present it with CUSTOM string, but it won't be valid
            # on update so that we force user to fix it and set it to something
            # supported. This can happen if user plays around with sharesec from
            # shell or has a domain admin hack settings via Computer Management MMC.
            perm = CUSTOM_ACCESS_MASK_STRING

        match ace.type:
            case security.SEC_ACE_TYPE_ACCESS_ALLOWED:
                ace_type = 'ALLOWED'
            case security.SEC_ACE_TYPE_ACCESS_DENIED:
                ace_type = 'DENIED'
            case _:
                raise ValueError(f'{ace.type}: unexpected ACE type')

        share_acl.append({
            'ae_who_sid': dom_sid,
            'ae_perm': perm,
            'ae_type': ace_type
        })

    return share_acl


def legacy_share_acl_string_to_sd_bytes(aclstr: str) -> bytes:
    """ Convert space-delimited ACL string into security descriptor bytes """
    share_acl = []
    for ace in aclstr.split():
        # sample ace: "S-1-1-0:ALLOWED/0x0/FULL"
        ae_who, ae_data = ace.split(':')
        ae_type, empty, ae_perm = ae_data.split('/')

        share_acl.append({'ae_who_sid': ae_who, 'ae_perm': ae_perm, 'ae_type': ae_type})

    return share_acl_to_sd_bytes(share_acl)
