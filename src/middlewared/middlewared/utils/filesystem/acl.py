import enum
import errno
import os

from typing import Any

from middlewared.service_exception import ValidationErrors

ACL_UNDEFINED_ID = -1


class ACLXattr(enum.StrEnum):
    POSIX_ACCESS = "system.posix_acl_access"
    POSIX_DEFAULT = "system.posix_acl_default"
    ZFS_NATIVE = "system.nfs4_acl_xdr"


ACL_XATTRS = frozenset([xat.value for xat in ACLXattr])

# ACCESS_ACL_XATTRS is set of ACLs that control access to the file itself.
ACCESS_ACL_XATTRS = frozenset([ACLXattr.POSIX_ACCESS.value, ACLXattr.ZFS_NATIVE.value])


def acl_is_present(xat_list: list[str]) -> bool:
    """
    This method returns boolean value if ACL is present in a list of extended
    attribute names. Both POSIX1E and our NFSv4 ACL implementations omit the
    xattr name from the list if it has no impact on permisssions (mode is
    authoritative.
    """
    return bool(set(xat_list) & ACL_XATTRS)


class FS_ACL_Type(enum.StrEnum):
    NFS4 = 'NFS4'
    POSIX1E = 'POSIX1E'
    DISABLED = 'DISABLED'


class NFS4ACE_Tag(enum.StrEnum):
    # See RFC-5661 Section 6.2.1.5
    # https://datatracker.ietf.org/doc/html/rfc5661#section-6.2.1.5
    #
    # Combination of NFS4ACE_Tag and id create the ACE Who field

    # Special identifiers
    SPECIAL_OWNER = 'owner@'  # file owner
    SPECIAL_GROUP = 'group@'  # file group
    SPECIAL_EVERYONE = 'everyone@'  # world (including owner and group)

    # Identifiers for regular user / group entries
    USER = 'USER'
    GROUP = 'GROUP'


class NFS4ACE_Type(enum.StrEnum):
    # See RFC-5661 Section 6.2.1.1
    # https://datatracker.ietf.org/doc/html/rfc5661#section-6.2.1.1
    ALLOW = 'ALLOW'
    DENY = 'DENY'


class NFS4ACE_Mask(enum.StrEnum):
    # See RFC-5661 Section 6.2.1.3.1
    # https://datatracker.ietf.org/doc/html/rfc5661#section-6.2.1.3.1
    READ_DATA = 'READ_DATA'
    WRITE_DATA = 'WRITE_DATA'
    APPEND_DATA = 'APPEND_DATA'
    READ_NAMED_ATTRS = 'READ_NAMED_ATTRS'
    WRITE_NAMED_ATTRS = 'WRITE_NAMED_ATTRS'
    EXECUTE = 'EXECUTE'
    DELETE = 'DELETE'
    DELETE_CHILD = 'DELETE_CHILD'
    READ_ATTRIBUTES = 'READ_ATTRIBUTES'
    WRITE_ATTRIBUTES = 'WRITE_ATTRIBUTES'
    READ_ACL = 'READ_ACL'
    WRITE_ACL = 'WRITE_ACL'
    WRITE_OWNER = 'WRITE_OWNER'
    SYNCHRONIZE = 'SYNCHRONIZE'


class NFS4ACE_MaskSimple(enum.StrEnum):
    # These are convenience access masks that are a combination of multiple
    # permissions defined in NFS4ACE_Mask above
    FULL_CONTROL = 'FULL_CONTROL'  # all perms above
    MODIFY = 'MODIFY'  # all perms except WRITE_ACL and WRITE_OWNER
    READ = 'READ'  # READ | READ_NAMED_ATTRS | READ_ATTRIBUTES | EXECUTE
    TRAVERSE = 'TRAVERSE'  # READ_NAMED_ATTRS | READ_ATTRIBUTES | EXECUTE


class NFS4ACE_Flag(enum.StrEnum):
    # See RFC-5661 Section 6.2.1.4.1
    # https://datatracker.ietf.org/doc/html/rfc5661#section-6.2.1.4.1
    FILE_INHERIT = 'FILE_INHERIT'
    DIRECTORY_INHERIT = 'DIRECTORY_INHERIT'
    NO_PROPAGATE_INHERIT = 'NO_PROPAGATE_INHERIT'
    INHERIT_ONLY = 'INHERIT_ONLY'
    INHERITED = 'INHERITED'


class NFS4ACE_FlagSimple(enum.StrEnum):
    # These are convenience access masks that are a combination of multiple
    # permissions defined in NFS4ACE_Mask above
    INHERIT = 'INHERIT'  # FILE_INHERIT | DIRECTORY_INHERIT
    NOINHERIT = 'NOINHERIT'  # ace flags = 0


class NFS4ACL_Flag(enum.StrEnum):
    # See RFC-5661 Section 6.4.3.2
    # https://datatracker.ietf.org/doc/html/rfc5661#section-6.4.3.2
    AUTOINHERIT = 'autoinherit'
    PROTECTED = 'protected'
    DEFAULTED = 'defaulted'


class POSIXACE_Tag(enum.StrEnum):
    # UGO entries
    USER_OBJ = 'USER_OBJ'  # file owner
    GROUP_OBJ = 'GROUP_OBJ'  # file group
    OTHER = 'OTHER'  # other

    MASK = 'MASK'  # defines maximum permissions granted to extended entries

    # Identifiers for regular user / group entries
    USER = 'USER'
    GROUP = 'GROUP'


class POSIXACE_Mask(enum.StrEnum):
    READ = 'READ'
    WRITE = 'WRITE'
    EXECUTE = 'EXECUTE'


NFS4_SPECIAL_ENTRIES = frozenset([
    NFS4ACE_Tag.SPECIAL_OWNER,
    NFS4ACE_Tag.SPECIAL_GROUP,
    NFS4ACE_Tag.SPECIAL_EVERYONE,
])

POSIX_SPECIAL_ENTRIES = frozenset([
    POSIXACE_Tag.USER_OBJ,
    POSIXACE_Tag.GROUP_OBJ,
    POSIXACE_Tag.OTHER,
    POSIXACE_Tag.MASK,
])


def validate_nfs4_ace_full(ace_in: dict[str, Any], schema_prefix: str, verrors: ValidationErrors) -> None:
    """
    This is further validation that occurs in filesystem.setacl. By this point
    ACE should have already passed through `validate_nfs4_ace_model` above.
    """
    if not isinstance(ace_in, dict):
        raise TypeError(f'{type(ace_in)}: expected dict')

    if ace_in['tag'] in NFS4_SPECIAL_ENTRIES:
        if ace_in['type'] == NFS4ACE_Type.DENY:
            tag = ace_in['tag']
            verrors.add(
                f'{schema_prefix}.tag',
                f'{tag}: DENY entries for specified tag are not permitted.'
            )
    else:
        ace_id = ace_in.get('id', ACL_UNDEFINED_ID)
        ace_who = ace_in.get('who')

        if ace_id != ACL_UNDEFINED_ID and ace_who:
            verrors.add(
                f'{schema_prefix}.who',
                f'Numeric ID {ace_id} and account name {ace_who} may not be specified simultaneously'
            )


def path_get_acltype(path: str) -> FS_ACL_Type:
    try:
        # ACCESS ACL is sufficient to determine POSIX ACL support
        os.getxattr(path, ACLXattr.POSIX_ACCESS)
        return FS_ACL_Type.POSIX1E

    except OSError as e:
        if e.errno == errno.ENODATA:
            # No ACL set, but zfs acltype is set to POSIX
            return FS_ACL_Type.POSIX1E

        # EOPNOTSUPP means that ZFS acltype is not set to POSIX
        if e.errno != errno.EOPNOTSUPP:
            raise

    try:
        os.getxattr(path, ACLXattr.ZFS_NATIVE)
        return FS_ACL_Type.NFS4
    except OSError as e:
        # ZFS acltype is not set to NFS4 which means it's disabled
        if e.errno == errno.EOPNOTSUPP:
            return FS_ACL_Type.DISABLED

        raise


def normalize_acl_ids(setacl_data: dict[str, Any]) -> None:
    for key in ('uid', 'gid'):
        if setacl_data[key] is None:
            setacl_data[key] = ACL_UNDEFINED_ID

    for ace in setacl_data['dacl']:
        if ace['id'] is None:
            ace['id'] = ACL_UNDEFINED_ID


def strip_acl_path(path: str) -> None:
    for xat in os.listxattr(path):
        if xat in ACL_XATTRS:
            os.removexattr(path, xat)
