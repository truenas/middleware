"""
Round-trip conversion tests for NFS4 and POSIX ACL dict<->obj helpers.

  nfs4acl_dict_to_obj  / nfs4acl_obj_to_dict
  posixacl_dict_to_obj / posixacl_obj_to_dict

These tests require truenas_os (only available on a TrueNAS system) but do
not touch the filesystem: they only exercise the pure-Python data-
transformation logic in middlewared.utils.filesystem.acl.
"""

import truenas_os as t

from middlewared.utils.filesystem.acl import (
    nfs4acl_dict_to_obj,
    nfs4acl_obj_to_dict,
    posixacl_dict_to_obj,
    posixacl_obj_to_dict,
)


# ---------------------------------------------------------------------------
# Helpers shared by both test classes
# ---------------------------------------------------------------------------

# Default all-False dicts matching the exact key-sets produced by
# nfs4acl_obj_to_dict / posixacl_obj_to_dict.
_NFS4_PERMS_NONE = dict.fromkeys(
    ('READ_DATA', 'WRITE_DATA', 'APPEND_DATA', 'READ_NAMED_ATTRS',
     'WRITE_NAMED_ATTRS', 'EXECUTE', 'DELETE', 'DELETE_CHILD',
     'READ_ATTRIBUTES', 'WRITE_ATTRIBUTES', 'READ_ACL', 'WRITE_ACL',
     'WRITE_OWNER', 'SYNCHRONIZE'),
    False,
)
_NFS4_FLAGS_NONE = dict.fromkeys(
    ('FILE_INHERIT', 'DIRECTORY_INHERIT', 'NO_PROPAGATE_INHERIT',
     'INHERIT_ONLY', 'INHERITED'),
    False,
)
_NFS4_ACLFLAGS_NONE = dict.fromkeys(('autoinherit', 'protected', 'defaulted'), False)
_POSIX_PERMS_NONE = dict.fromkeys(('READ', 'WRITE', 'EXECUTE'), False)


def _nfs4_perms(**on):
    return {**_NFS4_PERMS_NONE, **on}


def _nfs4_flags(**on):
    return {**_NFS4_FLAGS_NONE, **on}


def _nfs4_aclflags(**on):
    return {**_NFS4_ACLFLAGS_NONE, **on}


def _posix_perms(**on):
    return {**_POSIX_PERMS_NONE, **on}


# ---------------------------------------------------------------------------
# NFS4 round-trip: dict → obj → dict  (simplified=False)
# ---------------------------------------------------------------------------

def _nfs4_rt(acl_list, aclflags=None, uid=0, gid=0):
    """Full dict→obj→dict round-trip; returns (acl_list_out, aclflags_out)."""
    obj = nfs4acl_dict_to_obj(acl_list, aclflags)
    result = nfs4acl_obj_to_dict(obj, uid, gid, simplified=False)
    return result['acl'], result['aclflags']


class TestNFS4RoundTrip:

    def test_special_entries(self):
        """owner@, group@, everyone@ ALLOW ACEs survive round-trip."""
        acl_in = [
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True, READ_ATTRIBUTES=True),
             'flags': _nfs4_flags()},
            {'tag': 'group@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True),
             'flags': _nfs4_flags()},
            {'tag': 'everyone@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(),
             'flags': _nfs4_flags()},
        ]
        acl_out, aclflags_out = _nfs4_rt(acl_in)
        assert acl_out == acl_in
        assert aclflags_out == _nfs4_aclflags()

    def test_named_user(self):
        """Named USER entry preserves tag, id, type, perms, and flags."""
        acl_in = [
            {'tag': 'USER', 'id': 1000, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True, EXECUTE=True, READ_ATTRIBUTES=True),
             'flags': _nfs4_flags()},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_named_group(self):
        """Named GROUP entry preserves tag, id, type, perms, and flags."""
        acl_in = [
            {'tag': 'GROUP', 'id': 2000, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True),
             'flags': _nfs4_flags()},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_deny_type(self):
        """DENY ACE type is preserved through the round-trip."""
        acl_in = [
            {'tag': 'USER', 'id': 500, 'type': 'DENY',
             'perms': _nfs4_perms(WRITE_DATA=True, WRITE_ATTRIBUTES=True),
             'flags': _nfs4_flags()},
            {'tag': 'everyone@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True, WRITE_DATA=True),
             'flags': _nfs4_flags()},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_inheritance_flags(self):
        """FILE_INHERIT and DIRECTORY_INHERIT survive round-trip."""
        acl_in = [
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True),
             'flags': _nfs4_flags(FILE_INHERIT=True, DIRECTORY_INHERIT=True)},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_inherited_flag(self):
        """INHERITED flag survives round-trip."""
        acl_in = [
            {'tag': 'GROUP', 'id': 100, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True, EXECUTE=True),
             'flags': _nfs4_flags(INHERITED=True)},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_no_propagate_inherit_only_flags(self):
        """NO_PROPAGATE_INHERIT and INHERIT_ONLY survive round-trip."""
        acl_in = [
            {'tag': 'everyone@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True),
             'flags': _nfs4_flags(FILE_INHERIT=True, DIRECTORY_INHERIT=True,
                                  NO_PROPAGATE_INHERIT=True, INHERIT_ONLY=True)},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_acl_flag_autoinherit(self):
        """NFS4ACL autoinherit flag survives round-trip."""
        acl_in = [
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True), 'flags': _nfs4_flags()},
        ]
        _, aclflags_out = _nfs4_rt(acl_in, aclflags={'autoinherit': True})
        assert aclflags_out == _nfs4_aclflags(autoinherit=True)

    def test_acl_flag_protected(self):
        """NFS4ACL protected flag survives round-trip."""
        acl_in = [
            {'tag': 'everyone@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(), 'flags': _nfs4_flags()},
        ]
        _, aclflags_out = _nfs4_rt(acl_in, aclflags={'protected': True})
        assert aclflags_out == _nfs4_aclflags(protected=True)

    def test_acl_flag_defaulted(self):
        """NFS4ACL defaulted flag survives round-trip."""
        acl_in = [
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(), 'flags': _nfs4_flags()},
        ]
        _, aclflags_out = _nfs4_rt(acl_in, aclflags={'defaulted': True})
        assert aclflags_out == _nfs4_aclflags(defaulted=True)

    def test_none_aclflags_yields_all_false(self):
        """None aclflags input produces an all-False aclflags dict."""
        acl_in = [
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(), 'flags': _nfs4_flags()},
        ]
        _, aclflags_out = _nfs4_rt(acl_in, aclflags=None)
        assert aclflags_out == _nfs4_aclflags()

    def test_all_permissions(self):
        """All 14 NFS4 permissions survive round-trip."""
        all_perms = dict.fromkeys(_NFS4_PERMS_NONE, True)
        acl_in = [
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': all_perms, 'flags': _nfs4_flags()},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_multi_ace_ordering_preserved(self):
        """Relative ordering within DENY/ALLOW groups is preserved.

        truenas_os.NFS4ACL canonicalizes ACEs to DENY-before-ALLOW order
        while preserving relative order within each group.  The input must
        already be in canonical order for the round-trip to be stable.
        """
        acl_in = [
            # DENY entries first (canonical)
            {'tag': 'USER', 'id': 42, 'type': 'DENY',
             'perms': _nfs4_perms(WRITE_DATA=True),
             'flags': _nfs4_flags()},
            {'tag': 'everyone@', 'id': -1, 'type': 'DENY',
             'perms': _nfs4_perms(WRITE_ACL=True, WRITE_OWNER=True),
             'flags': _nfs4_flags()},
            # ALLOW entries after
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True, WRITE_DATA=True),
             'flags': _nfs4_flags(FILE_INHERIT=True)},
            {'tag': 'group@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(READ_DATA=True),
             'flags': _nfs4_flags()},
        ]
        acl_out, _ = _nfs4_rt(acl_in)
        assert acl_out == acl_in

    def test_uid_gid_passthrough(self):
        """uid/gid values are passed through nfs4acl_obj_to_dict unchanged."""
        acl_in = [
            {'tag': 'owner@', 'id': -1, 'type': 'ALLOW',
             'perms': _nfs4_perms(), 'flags': _nfs4_flags()},
        ]
        obj = nfs4acl_dict_to_obj(acl_in, None)
        result = nfs4acl_obj_to_dict(obj, uid=1001, gid=2002, simplified=False)
        assert result['uid'] == 1001
        assert result['gid'] == 2002


# ---------------------------------------------------------------------------
# NFS4 round-trip: obj → dict (simplified=True) → obj → dict (simplified=False)
#
# A simplified dict uses BASIC shortcuts (e.g. {'BASIC': 'FULL_CONTROL'}).
# After one more conversion the result must equal the direct simplified=False
# rendering of the original object.
# ---------------------------------------------------------------------------

_NFS4_FULL_MASK = (
    t.NFS4Perm.READ_DATA | t.NFS4Perm.WRITE_DATA |
    t.NFS4Perm.APPEND_DATA | t.NFS4Perm.READ_NAMED_ATTRS |
    t.NFS4Perm.WRITE_NAMED_ATTRS | t.NFS4Perm.EXECUTE |
    t.NFS4Perm.DELETE_CHILD | t.NFS4Perm.READ_ATTRIBUTES |
    t.NFS4Perm.WRITE_ATTRIBUTES | t.NFS4Perm.DELETE |
    t.NFS4Perm.READ_ACL | t.NFS4Perm.WRITE_ACL |
    t.NFS4Perm.WRITE_OWNER | t.NFS4Perm.SYNCHRONIZE
)


def _obj_simplified_rt(aces, acl_flags=None):
    """
    obj → simplified dict → obj → full dict.
    Also returns the intermediate simplified dict for spot-checks.
    """
    if acl_flags is None:
        acl_flags = t.NFS4ACLFlag(0)
    acl1 = t.NFS4ACL.from_aces(aces, acl_flags)
    simplified = nfs4acl_obj_to_dict(acl1, uid=0, gid=0, simplified=True)
    acl2 = nfs4acl_dict_to_obj(simplified['acl'], simplified['aclflags'])
    full = nfs4acl_obj_to_dict(acl2, uid=0, gid=0, simplified=False)
    return simplified, full


def _obj_full_dict(aces, acl_flags=None):
    if acl_flags is None:
        acl_flags = t.NFS4ACLFlag(0)
    return nfs4acl_obj_to_dict(t.NFS4ACL.from_aces(aces, acl_flags),
                               uid=0, gid=0, simplified=False)


class TestNFS4SimplifiedRoundTrip:

    def test_full_control_basic_perm(self):
        """FULL_CONTROL mask is rendered as BASIC in simplified mode and
        round-trips back to the same full permission set."""
        aces = [t.NFS4Ace(t.NFS4AceType.ALLOW, t.NFS4Flag(0),
                          _NFS4_FULL_MASK, t.NFS4Who.OWNER, -1)]
        simplified, full = _obj_simplified_rt(aces)

        assert simplified['acl'][0]['perms'] == {'BASIC': 'FULL_CONTROL'}
        assert full['acl'] == _obj_full_dict(aces)['acl']

    def test_modify_basic_perm(self):
        """MODIFY mask is rendered as BASIC in simplified mode."""
        modify_mask = _NFS4_FULL_MASK & ~(t.NFS4Perm.WRITE_ACL | t.NFS4Perm.WRITE_OWNER)
        aces = [t.NFS4Ace(t.NFS4AceType.ALLOW, t.NFS4Flag(0),
                          modify_mask, t.NFS4Who.GROUP, -1)]
        simplified, full = _obj_simplified_rt(aces)

        assert simplified['acl'][0]['perms'] == {'BASIC': 'MODIFY'}
        assert full['acl'] == _obj_full_dict(aces)['acl']

    def test_read_basic_perm(self):
        """READ mask is rendered as BASIC in simplified mode."""
        read_mask = (t.NFS4Perm.READ_DATA | t.NFS4Perm.READ_NAMED_ATTRS |
                     t.NFS4Perm.READ_ATTRIBUTES | t.NFS4Perm.READ_ACL |
                     t.NFS4Perm.EXECUTE | t.NFS4Perm.SYNCHRONIZE)
        aces = [t.NFS4Ace(t.NFS4AceType.ALLOW, t.NFS4Flag(0),
                          read_mask, t.NFS4Who.EVERYONE, -1)]
        simplified, full = _obj_simplified_rt(aces)

        assert simplified['acl'][0]['perms'] == {'BASIC': 'READ'}
        assert full['acl'] == _obj_full_dict(aces)['acl']

    def test_inherit_basic_flag(self):
        """FILE_INHERIT|DIRECTORY_INHERIT is rendered as BASIC INHERIT and
        round-trips back to the same flag set."""
        fi_di = t.NFS4Flag.FILE_INHERIT | t.NFS4Flag.DIRECTORY_INHERIT
        aces = [t.NFS4Ace(t.NFS4AceType.ALLOW, fi_di,
                          t.NFS4Perm.READ_DATA, t.NFS4Who.EVERYONE, -1)]
        simplified, full = _obj_simplified_rt(aces)

        assert simplified['acl'][0]['flags'] == {'BASIC': 'INHERIT'}
        assert full['acl'] == _obj_full_dict(aces)['acl']

    def test_noinherit_basic_flag(self):
        """Zero flags renders as BASIC NOINHERIT and round-trips cleanly."""
        aces = [t.NFS4Ace(t.NFS4AceType.ALLOW, t.NFS4Flag(0),
                          t.NFS4Perm.READ_DATA, t.NFS4Who.OWNER, -1)]
        simplified, full = _obj_simplified_rt(aces)

        assert simplified['acl'][0]['flags'] == {'BASIC': 'NOINHERIT'}
        assert full['acl'] == _obj_full_dict(aces)['acl']


# ---------------------------------------------------------------------------
# POSIX round-trip: dict → obj → dict
# ---------------------------------------------------------------------------

def _posix_rt(acl_list, uid=0, gid=0):
    """Full dict→obj→dict round-trip; returns acl_list_out."""
    result = posixacl_obj_to_dict(posixacl_dict_to_obj(acl_list), uid, gid)
    return result['acl']


class TestPOSIXRoundTrip:

    def test_minimal_acl(self):
        """Minimal USER_OBJ / GROUP_OBJ / OTHER entries survive round-trip."""
        acl_in = [
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True)},
        ]
        assert _posix_rt(acl_in) == acl_in

    def test_with_mask(self):
        """MASK entry survives round-trip."""
        acl_in = [
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'MASK', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms()},
        ]
        assert _posix_rt(acl_in) == acl_in

    def test_named_user(self):
        """Named USER entry preserves tag and id."""
        acl_in = [
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'USER', 'id': 1000, 'default': False,
             'perms': _posix_perms(READ=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'MASK', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms()},
        ]
        assert _posix_rt(acl_in) == acl_in

    def test_named_group(self):
        """Named GROUP entry preserves tag and id."""
        acl_in = [
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'GROUP', 'id': 2000, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'MASK', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms()},
        ]
        assert _posix_rt(acl_in) == acl_in

    def test_default_entries(self):
        """Default ACEs are preserved separately from access ACEs, in
        access-first / default-second output order."""
        acl_in = [
            # access entries
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'MASK', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms()},
            # default entries
            {'tag': 'USER_OBJ', 'id': -1, 'default': True,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': True,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'MASK', 'id': -1, 'default': True,
             'perms': _posix_perms(READ=True, EXECUTE=True)},
            {'tag': 'OTHER', 'id': -1, 'default': True,
             'perms': _posix_perms()},
        ]
        assert _posix_rt(acl_in) == acl_in

    def test_all_perms_set(self):
        """All three POSIX permissions survive round-trip."""
        acl_in = [
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
        ]
        assert _posix_rt(acl_in) == acl_in

    def test_no_perms(self):
        """All-False POSIX permissions survive round-trip."""
        acl_in = [
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms()},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms()},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms()},
        ]
        assert _posix_rt(acl_in) == acl_in

    def test_uid_gid_passthrough(self):
        """uid/gid values are passed through posixacl_obj_to_dict unchanged."""
        acl_in = [
            {'tag': 'USER_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True, WRITE=True, EXECUTE=True)},
            {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
             'perms': _posix_perms(READ=True)},
            {'tag': 'OTHER', 'id': -1, 'default': False,
             'perms': _posix_perms()},
        ]
        result = posixacl_obj_to_dict(posixacl_dict_to_obj(acl_in), uid=500, gid=600)
        assert result['uid'] == 500
        assert result['gid'] == 600


# ---------------------------------------------------------------------------
# POSIX generate_inherited_acl: file vs directory variants
#
# Covers the invariant relied on by acltool()'s CLONE/INHERIT path:
# generate_inherited_acl(is_dir=False) must never produce an ACL with default
# entries (default entries are only valid on directories; fsetacl() raises
# ValueError if you try to set them on a file).
# ---------------------------------------------------------------------------

def _posix_acl_with_defaults():
    """Return a POSIXACL that has both access and default entries."""
    rwx = t.POSIXPerm.READ | t.POSIXPerm.WRITE | t.POSIXPerm.EXECUTE
    aces = [
        t.POSIXAce(t.POSIXTag.USER_OBJ,  rwx,             default=False),
        t.POSIXAce(t.POSIXTag.GROUP_OBJ, rwx,             default=False),
        t.POSIXAce(t.POSIXTag.OTHER,     t.POSIXPerm(0),  default=False),
        t.POSIXAce(t.POSIXTag.USER_OBJ,  rwx,             default=True),
        t.POSIXAce(t.POSIXTag.GROUP_OBJ, rwx,             default=True),
        t.POSIXAce(t.POSIXTag.OTHER,     t.POSIXPerm(0),  default=True),
    ]
    return t.POSIXACL.from_aces(aces)


class TestPOSIXGenerateInheritedAcl:

    def test_file_variant_has_no_default_entries(self):
        """generate_inherited_acl(is_dir=False) must produce no default entries.

        acltool() relies on this guarantee when applying a POSIX ACL to files
        during recursive CLONE/INHERIT operations.  Passing a POSIXACL with
        default entries to fsetacl() on a file raises ValueError.
        """
        file_acl = _posix_acl_with_defaults().generate_inherited_acl(is_dir=False)
        assert not file_acl.default_aces, (
            'file-variant ACL must have no default entries'
        )

    def test_dir_variant_has_default_entries(self):
        """generate_inherited_acl(is_dir=True) must preserve default entries."""
        dir_acl = _posix_acl_with_defaults().generate_inherited_acl(is_dir=True)
        assert dir_acl.default_aces, (
            'dir-variant ACL must carry default entries'
        )

    def test_file_variant_has_access_entries(self):
        """generate_inherited_acl(is_dir=False) must still produce access entries."""
        file_acl = _posix_acl_with_defaults().generate_inherited_acl(is_dir=False)
        assert file_acl.aces, (
            'file-variant ACL must have access entries'
        )


# ---------------------------------------------------------------------------
# POSIX generate_inherited_acl: file vs directory variants
#
# Covers the invariant relied on by acltool()'s CLONE/INHERIT path:
# generate_inherited_acl(is_dir=False) must never produce an ACL with default
# entries (default entries are only valid on directories; fsetacl() raises
# ValueError if you try to set them on a file).
# ---------------------------------------------------------------------------

def _posix_acl_with_defaults():
    """Return a POSIXACL that has both access and default entries."""
    rwx = t.POSIXPerm.READ | t.POSIXPerm.WRITE | t.POSIXPerm.EXECUTE
    aces = [
        t.POSIXAce(t.POSIXTag.USER_OBJ,  rwx,             default=False),
        t.POSIXAce(t.POSIXTag.GROUP_OBJ, rwx,             default=False),
        t.POSIXAce(t.POSIXTag.OTHER,     t.POSIXPerm(0),  default=False),
        t.POSIXAce(t.POSIXTag.USER_OBJ,  rwx,             default=True),
        t.POSIXAce(t.POSIXTag.GROUP_OBJ, rwx,             default=True),
        t.POSIXAce(t.POSIXTag.OTHER,     t.POSIXPerm(0),  default=True),
    ]
    return t.POSIXACL.from_aces(aces)


class TestPOSIXGenerateInheritedAcl:

    def test_file_variant_has_no_default_entries(self):
        """generate_inherited_acl(is_dir=False) must produce no default entries.

        acltool() relies on this guarantee when applying a POSIX ACL to files
        during recursive CLONE/INHERIT operations.  Passing a POSIXACL with
        default entries to fsetacl() on a file raises ValueError.
        """
        file_acl = _posix_acl_with_defaults().generate_inherited_acl(is_dir=False)
        assert not file_acl.default_aces, (
            'file-variant ACL must have no default entries'
        )

    def test_dir_variant_has_default_entries(self):
        """generate_inherited_acl(is_dir=True) must preserve default entries."""
        dir_acl = _posix_acl_with_defaults().generate_inherited_acl(is_dir=True)
        assert dir_acl.default_aces, (
            'dir-variant ACL must carry default entries'
        )

    def test_file_variant_has_access_entries(self):
        """generate_inherited_acl(is_dir=False) must still produce access entries."""
        file_acl = _posix_acl_with_defaults().generate_inherited_acl(is_dir=False)
        assert file_acl.aces, (
            'file-variant ACL must have access entries'
        )
