import os

import truenas_os

from middlewared.utils.filesystem import directory
from middlewared.utils.filesystem.acl import statx_acl_is_trivial
from middlewared.utils.filesystem.stat_x import STATX_DEFAULT_MASK

T = truenas_os.POSIXTag
P = truenas_os.POSIXPerm


def posix_aces(named, default=False):
    """The entries the mode makes, and with `named` a user behind a mask, which the mode cannot say."""
    aces = [
        truenas_os.POSIXAce(tag=T.USER_OBJ, perms=P.READ | P.WRITE, default=default),
        truenas_os.POSIXAce(tag=T.GROUP_OBJ, perms=P.READ, default=default),
        truenas_os.POSIXAce(tag=T.OTHER, perms=P(0), default=default),
    ]
    if named:
        aces += [
            truenas_os.POSIXAce(tag=T.USER, perms=P.READ, id=8675309, default=default),
            truenas_os.POSIXAce(tag=T.MASK, perms=P.READ, default=default),
        ]
    return aces


def make_tree(path):
    """A file with no ACL, a file with an access ACL and a folder with a default ACL alone, on tmpfs."""
    for name in ("plain", "named"):
        open(os.path.join(path, name), "w").close()
    os.mkdir(os.path.join(path, "inherits"))
    acls = {"named": posix_aces(named=True), "inherits": posix_aces(named=False) + posix_aces(named=True, default=True)}
    for name, aces in acls.items():
        fd = os.open(os.path.join(path, name), os.O_RDONLY)
        try:
            truenas_os.fsetacl(fd, truenas_os.POSIXACL.from_aces(aces))
        finally:
            os.close(fd)


def test_statx_says_which_files_have_a_posix_acl(tmpdir):
    make_tree(tmpdir)
    for name, trivial in {"plain": True, "named": False, "inherits": False}.items():
        st = truenas_os.statx(os.path.join(tmpdir, name), mask=STATX_DEFAULT_MASK)
        assert st.stx_mask & truenas_os.STATX_ACL, "the kernel answers STATX_ACL"
        assert statx_acl_is_trivial(st) is trivial, name


def test_listdir_lists_the_xattrs_of_an_entry_with_an_acl_alone(tmpdir, monkeypatch):
    make_tree(tmpdir)
    calls = []
    listxattr = os.listxattr

    def counted(fd):
        calls.append(fd)
        return listxattr(fd)

    monkeypatch.setattr(directory.os, "listxattr", counted)
    with directory.DirectoryIterator(str(tmpdir), request_mask=directory.DirectoryRequestMask.ACL) as entries:
        assert {entry["name"]: entry["acl"] for entry in entries} == {"plain": False, "named": True, "inherits": True}
    assert len(calls) == 2, "the file with no ACL is answered from statx alone"
