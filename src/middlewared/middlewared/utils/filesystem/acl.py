import enum


class ACLXattr(enum.Enum):
    POSIX_ACCESS = "system.posix_acl_access"
    POSIX_DEFAULT = "system.posix_acl_default"
    ZFS_NATIVE = "system.nfs4_acl_xdr"


ACL_XATTRS = set([xat.value for xat in ACLXattr])

# ACCESS_ACL_XATTRS is set of ACLs that control access to the file itself.
ACCESS_ACL_XATTRS = set([ACLXattr.POSIX_ACCESS.value, ACLXattr.ZFS_NATIVE.value])


def acl_is_present(xat_list: list) -> bool:
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
    EXECUTE = 'EXECUTE'
    DELETE = 'DELETE'
    DELETE_CHILD = 'DELETE_CHILD'
    READ_ATTRIBUTES = 'READ_ATTRIBUTES'
    WRITE_ATTRIBUTES = 'WRITE_ATTRIBUTES'
    READ_ACL = 'READ_ACL'
    WRITE_ACL = 'WRITE_ACL'
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
