import enum
import subprocess

from middlewared.service_exception import CallError, ValidationErrors
from middlewared.utils.filesystem.acl import (
    ACL_UNDEFINED_ID,
    FS_ACL_Type,
    NFS4ACE_Flag,
    NFS4ACE_FlagSimple,
)


class AclToolAction(enum.StrEnum):
    CHOWN = 'chown'  # Only chown files
    CLONE = 'clone'  # Use simplified imheritance logic
    INHERIT = 'inherit'  # NFS41-style inheritance
    STRIP = 'strip'  # Strip ACL from specified path
    RESTORE = 'restore'  # restore ACL from snapshot


def acltool(path: str, action: AclToolAction, uid: int, gid: int, options: dict) -> None:
    """
    This is an internal-only tool that performs certain ACL-related operations on the specified path.
    """
    flags = "-r"
    flags += "x" if options.get('traverse') else ""
    flags += "C" if options.get('do_chmod') else ""
    flags += "P" if options.get('posixacl') else ""

    acltool = subprocess.run([
        '/usr/bin/nfs4xdr_winacl',
        '-a', action,
        '-O', str(uid), '-G', str(gid),
        flags,
        '-c', path,
        '-p', path], check=False, capture_output=True
    )
    if acltool.returncode != 0:
        raise CallError(f"acltool [{action}] on path {path} failed with error: [{acltool.stderr.decode().strip()}]")


def __ace_is_inherited_nfs4(ace):
    if ace['flags'].get('BASIC'):
        return False

    return ace['flags'].get(NFS4ACE_Flag.INHERITED, False)


def canonicalize_nfs4_acl(theacl):
    """
    Order NFS4 ACEs according to MS guidelines:
    1) Deny ACEs that apply to the object itself (NOINHERIT)
    2) Allow ACEs that apply to the object itself (NOINHERIT)
    3) Deny ACEs that apply to a subobject of the object (INHERIT)
    4) Allow ACEs that apply to a subobject of the object (INHERIT)

    See http://docs.microsoft.com/en-us/windows/desktop/secauthz/order-of-aces-in-a-dacl
    Logic is simplified here because we do not determine depth from which ACLs are inherited.
    """
    out = []
    acl_groups = {
        "deny_noinherit": [],
        "deny_inherit": [],
        "allow_noinherit": [],
        "allow_inherit": [],
    }

    for ace in theacl:
        key = f'{ace.get("type", "ALLOW").lower()}_{"inherit" if __ace_is_inherited_nfs4(ace) else "noinherit"}'
        acl_groups[key].append(ace)

    for g in acl_groups.values():
        out.extend(g)

    return out


def __calculate_inherited_posix1e(theacl, isdir):
    """
    Create a new ACL based on what a file or directory would receive if it
    were created within a directory that had `theacl` set on it.
    """
    inherited = []
    for entry in theacl['acl']:
        if entry['default'] is False:
            continue

        # add access entry
        inherited.append(entry.copy() | {'default': False})

        if isdir:
            # add default entry
            inherited.append(entry)

    return inherited


def __calculate_inherited_nfs4(theacl, isdir):
    """
    Create a new ACL based on what a file or directory would receive if it
    were created within a directory that had `theacl` set on it.
    """
    inherited = []
    for entry in theacl['acl']:
        if not (flags := entry.get('flags', {}).copy()):
            continue

        if (basic := flags.get('BASIC')) == NFS4ACE_FlagSimple.NOINHERIT:
            continue
        elif basic == NFS4ACE_FlagSimple.INHERIT:
            flags[NFS4ACE_Flag.INHERITED] = True
            inherited.append(entry)
            continue
        elif not flags.get(NFS4ACE_Flag.FILE_INHERIT, False) and not flags.get(NFS4ACE_Flag.DIRECTORY_INHERIT, False):
            # Entry has no inherit flags
            continue
        elif not isdir and not flags.get(NFS4ACE_Flag.FILE_INHERIT):
            # File and this entry doesn't inherit on files
            continue

        if isdir:
            if not flags.get(NFS4ACE_Flag.DIRECTORY_INHERIT, False):
                if flags[NFS4ACE_Flag.NO_PROPAGATE_INHERIT]:
                    # doesn't apply to this dir and shouldn't apply to contents.
                    continue

                # This is a directory ACL and we have entry that only applies to files.
                flags[NFS4ACE_Flag.INHERIT_ONLY] = True
            elif flags.get(NFS4ACE_Flag.INHERIT_ONLY, False):
                flags[NFS4ACE_Flag.INHERIT_ONLY] = False
            elif flags.get(NFS4ACE_Flag.NO_PROPAGATE_INHERIT):
                flags[NFS4ACE_Flag.DIRECTORY_INHERIT] = False
                flags[NFS4ACE_Flag.FILE_INHERIT] = False
                flags[NFS4ACE_Flag.NO_PROPAGATE_INHERIT] = False
        else:
            flags[NFS4ACE_Flag.DIRECTORY_INHERIT] = False
            flags[NFS4ACE_Flag.FILE_INHERIT] = False
            flags[NFS4ACE_Flag.NO_PROPAGATE_INHERIT] = False
            flags[NFS4ACE_Flag.INHERIT_ONLY] = False

        inherited.append({
            'tag': entry['tag'],
            'id': entry['id'],
            'type': entry['type'],
            'perms': entry['perms'],
            'flags': flags | {NFS4ACE_Flag.INHERITED: True}
        })

    return inherited


def calculate_inherited_acl(theacl, isdir=True):
    """
    Create a new ACL based on what a file or directory would receive if it
    were created within a directory that had `theacl` set on it.

    This is intended to be used for determining new ACL to set on a dataset
    that is created (in certain scenarios) to meet user expectations of
    inheritance.
    """
    acltype = FS_ACL_Type(theacl['acltype'])

    match acltype:
        case FS_ACL_Type.POSIX1E:
            return __calculate_inherited_posix1e(theacl, isdir)

        case FS_ACL_Type.NFS4:
            return __calculate_inherited_nfs4(theacl, isdir)

        case FS_ACL_Type.DISABLED:
            raise ValueError('ACL is disabled')

        case _:
            raise TypeError(f'{acltype}: unknown ACL type')


def gen_aclstring_posix1e(dacl: list, recursive: bool, verrors: ValidationErrors) -> str:
    """
    This method iterates through provided POSIX1e ACL and
    performs additional validation before returning the ACL
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

        if ace.get('who') and ace['id'] not in (None, ACL_UNDEFINED_ID):
            verrors.add(
                f'filesystem_acl.dacl.{idx}.who',
                f'Numeric ID {ace["id"]} and account name {ace["who"]} may not be specified simultaneously'
            )

        if ace['id'] == ACL_UNDEFINED_ID:
            ace['id'] = ''

        who = "DEF_" if ace['default'] else ""
        who += ace['tag']
        duplicate_who = has_tag.get(who)

        if duplicate_who is True:
            verrors.add(
                f'filesystem_acl.dacl.{idx}',
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
