import enum


class ACLXattr(enum.Enum):
    POSIX_ACCESS = "system.posix_acl_access"
    POSIX_DEFAULT = "system.posix_acl_default"
    ZFS_NATIVE = "system.nfs4_acl_xdr"


ACL_XATTRS = set([xat.value for xat in ACLXattr])


def acl_is_present(xat_list: list) -> bool:
    """
    This method returns boolean value if ACL is present in a list of extended
    attribute names. Both POSIX1E and our NFSv4 ACL implementations omit the
    xattr name from the list if it has no impact on permisssions (mode is
    authoritative.
    """
    return bool(set(xat_list) & ACL_XATTRS)
