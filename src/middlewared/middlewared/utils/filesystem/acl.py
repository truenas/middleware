import enum

from middlewared.service_exception import ValidationErrors


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


def validate_nfs4_ace_full(ace_in: dict) -> None:
    """
    This is further validation that occurs in filesystem.setacl. By this point
    ACE should have already passed through `validate_nfs4_ace_model` above.
    """
    if not isinstance(ace_in, dict):
        raise TypeError(f'{type(ace_in)}: expected dict')

    if ace_in['tag'] in NFS4_SPECIAL_ENTRIES:
        if ace_in['type'] == NFS4ACE_Type.DENY:
            raise ValueError(f'{ace_in["tag"]}: DENY entries for specified tag are not permitted.')

    else:
        if ace_in.get('id') is not None and ace_in.get('who'):
            raise ValueError('Numeric ID "id" and account name "who" may not be specified simultaneously')


def gen_aclstring_posix1e(dacl: list, recursive: bool, verrors: ValidationErrors) -> str:
    """
    This method iterates through provided POSIX1e ACL and
    performs addtional validation before returning the ACL
    string formatted for the setfacl command. In case
    of ValidationError, None is returned.
    """
    has_tag = {
        "USER_OBJ": False,
        "GROUP_OBJ": False,
        "OTHER": False,
        "MASK": False,
        "DEF_USER_OBJ": False,
        "DEF_GROUP_OBJ": False,
        "DEF_OTHER": False,
        "DEF_MASK": False,
    }
    required_entries = ["USER_OBJ", "GROUP_OBJ", "OTHER"]
    has_named = False
    has_def_named = False
    has_default = False
    aclstring = ""

    for idx, ace in enumerate(dacl):
        if idx != 0:
            aclstring += ","

        if ace['id'] == -1:
            ace['id'] = ''

        who = "DEF_" if ace['default'] else ""
        who += ace['tag']
        duplicate_who = has_tag.get(who)

        if duplicate_who is True:
            verrors.add(
                'filesystem_acl.dacl.{idx}',
                f'More than one {"default" if ace["default"] else ""} '
                f'{ace["tag"]} entry is not permitted'
            )

        elif duplicate_who is False:
            has_tag[who] = True

        if ace['tag'] in ["USER", "GROUP"]:
            if ace['default']:
                has_def_named = True
            else:
                has_named = True

        ace['tag'] = ace['tag'].rstrip('_OBJ').lower()

        if ace['default']:
            has_default = True
            aclstring += "default:"

        aclstring += f"{ace['tag']}:{ace['id']}:"
        aclstring += 'r' if ace['perms']['READ'] else '-'
        aclstring += 'w' if ace['perms']['WRITE'] else '-'
        aclstring += 'x' if ace['perms']['EXECUTE'] else '-'

    if has_named and not has_tag['MASK']:
        verrors.add(
            'filesystem_acl.dacl',
            'Named (user or group) POSIX ACL entries '
            'require a mask entry to be present in the ACL.'
        )


    elif has_def_named and not has_tag['DEF_MASK']:
        verrors.add(
            'filesystem_acl.dacl',
            'Named default (user or group) POSIX ACL entries '
            'require a default mask entry to be present in the ACL.'
        )

    if recursive and not has_default:
        verrors.add(
            'filesystem_acl.dacl',
            'Default ACL entries are required in order to apply '
            'ACL recursively.'
        )

    for entry in required_entries:
        if not has_tag[entry]:
            verrors.add(
                'filesystem_acl.dacl',
                f'Presence of [{entry}] entry is required.'
            )

        if has_default and not has_tag[f"DEF_{entry}"]:
            verrors.add(
                'filesystem_acl.dacl',
                f'Presence of default [{entry}] entry is required.'
            )

    return aclstring
