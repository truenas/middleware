from samba.samba3 import libsmb_samba_internal as libsmb
from samba.dcerpc import security
from samba.samba3 import param as s3param
from samba import credentials
import subprocess
import contextlib
import os
from samba import NTSTATUSError
from functions import SSH_TEST


class SMB(object):
    """
    Python implementation of basic SMB operations for protocol testing.
    This provides sufficient functionality to connect to remote SMB share,
    create and delete files, read, write, and list, make, and remove
    directories.

    Basic workflow can be something like this:

    c = SMB.connect(<ip address>, <share>, <username>, <password>)
    c.mkdir("testdir")
    fh = c.create_file("testdir/testfile")
    c.write(fh, b"Test base stream")
    fh2 = c.create_file("testdir/testfile:stream")
    c.write(fh, b"Test alternate data stream")
    c.read(fh)
    c.read(fh2)
    c.close(fh, True)
    c.ls("testdir")
    c.disconnect()
    """
    def __init__(self, **kwargs):
        self._connection = None
        self._open_files = {}
        self._cred = None
        self._lp = None
        self._user = None
        self._share = None
        self._host = None
        self._smb1 = False

    def connect(self, **kwargs):
        host = kwargs.get("host")
        share = kwargs.get("share")
        username = kwargs.get("username")
        password = kwargs.get("password")
        smb1 = kwargs.get("smb1", False)

        self._lp = s3param.get_context()
        self._lp.load_default()
        self._cred = credentials.Credentials()
        self._cred.guess(self._lp)

        if username is not None:
            self._cred.set_username(username)
        if password is not None:
            self._cred.set_password(password)

        self._host = host
        self._share = share
        self._smb1 = smb1
        self._connection = libsmb.Conn(
            host,
            share,
            self._lp,
            self._cred,
            force_smb1=smb1,
        )

    def disconnect(self):
        open_files = list(self._open_files.keys())
        try:
            for f in open_files:
                self.close(f)
        except NTSTATUSError:
            pass

        del(self._connection)
        del(self._cred)
        del(self._lp)

    def show_connection(self):
        return {
            "connected": self._connection.chkpath(''),
            "host": self._host,
            "share": self._share,
            "smb1": self._smb1,
            "username": self._user,
            "open_files": self._open_files,
        }

    def mkdir(self, path):
        return self._connection.mkdir(path)

    def rmdir(self, path):
        return self._connection.rmdir(path)

    def ls(self, path):
        return self._connection.list(path)

    def create_file(self, file, mode, attributes=None, do_create=False):
        dosmode = 0
        f = None
        for char in str(attributes):
            if char == "h":
                dosmode += libsmb.FILE_ATTRIBUTE_HIDDEN
            elif char == "r":
                dosmode += libsmb.FILE_ATTRIBUTE_READONLY
            elif char == "s":
                dosmode += libsmb.FILE_ATTRIBUTE_SYSTEM
            elif char == "a":
                dosmode += libsmb.FILE_ATTRIBUTE_ARCHIVE

        if mode == "r":
            f = self._connection.create(
                file,
                CreateDisposition=1 if not do_create else 3,
                DesiredAccess=security.SEC_GENERIC_READ,
                FileAttributes=dosmode,
            )
        elif mode == "w":
            f = self._connection.create(
                file,
                CreateDisposition=3,
                DesiredAccess=security.SEC_GENERIC_ALL,
                FileAttributes=dosmode,
            )

        self._open_files[f] = {
            "filename": file,
            "fh": f,
            "mode": mode,
            "attributes": dosmode
        }
        return f

    def close(self, idx, delete=False):
        if delete:
            self._connection.delete_on_close(
                self._open_files[idx]["fh"],
                True
            )
        self._connection.close(self._open_files[idx]["fh"])
        self._open_files.pop(idx)
        return self._open_files

    def read(self, idx=0, offset=0, cnt=1024):
        return self._connection.read(
            self._open_files[idx]["fh"], offset, cnt
        )

    def write(self, idx=0, data=None, offset=0):
        return self._connection.write(
            self._open_files[idx]["fh"], data, offset
        )

    def _parse_quota(self, quotaout):
        ret = []
        for entry in quotaout:
            e = entry.split(":")
            if len(e) != 2:
                continue

            user = e[0].strip()
            used, soft, hard = e[1].split("/")

            ret.append({
                "user": user,
                "used": int(used.strip()),
                "soft_limit": int(soft.strip()) if soft.strip() != "NO LIMIT" else None,
                "hard_limit": int(hard.strip()) if hard.strip() != "NO LIMIT" else None,
            })

        return ret

    def get_shadow_copies(self, **kwargs):
        snaps = []
        host = kwargs.get("host")
        share = kwargs.get("share")
        path = kwargs.get("path", "/")
        username = kwargs.get("username")
        password = kwargs.get("password")
        smb1 = kwargs.get("smb1", False)

        cmd = [
            "smbclient", f"//{host}/{share}",
            "-U", f"{username}%{password}",
        ]

        if smb1:
            cmd.extend(["-m", "NT1"])

        cmd.extend(["-c", f'allinfo {path}'])
        cl = subprocess.run(cmd, capture_output=True)
        if cl.returncode != 0:
            raise RuntimeError(cl.stderr.decode())

        client_out = cl.stdout.decode().splitlines()
        for i in client_out:
            if i.startswith("@GMT"):
                snaps.append(i)

        return snaps

    def get_quota(self, **kwargs):
        host = kwargs.get("host")
        share = kwargs.get("share")
        username = kwargs.get("username")
        password = kwargs.get("password")
        do_list = kwargs.get("list")
        smb1 = kwargs.get("smb1", False)

        cmd = [
            "smbcquotas", f"//{host}/{share}",
            "-U", f"{username}%{password}",
        ]
        if do_list:
            cmd.append("-L")

        if smb1:
            cmd.extend(["-m", "NT1"])

        smbcquotas = subprocess.run(cmd, capture_output=True)
        quotaout = smbcquotas.stdout.decode().splitlines()
        return self._parse_quota(quotaout)

    def set_quota(self, **kwargs):
        host = kwargs.get("host")
        share = kwargs.get("share")
        username = kwargs.get("username")
        password = kwargs.get("password")
        target = kwargs.get("target")
        hard_limit = kwargs.get("hardlimit", 0)
        soft_limit = kwargs.get("softlimit", 0)
        smb1 = kwargs.get("smb1", False)

        cmd = [
            "smbcquotas", f"//{host}/{share}",
            "-S", f"UQLIM:{target}:{soft_limit}/{hard_limit}",
            "-U", f"{username}%{password}",
        ]
        if smb1:
            cmd.extend(["-m", "NT1"])

        smbcquotas = subprocess.run(cmd, capture_output=True)
        quotaout = smbcquotas.stdout.decode().splitlines()
        return self._parse_quota(quotaout)


class NFS(object):
    perms = [
        "READ_DATA",
        "WRITE_DATA",
        "EXECUTE",
        "APPEND_DATA",
        "DELETE_CHILD",
        "DELETE",
        "READ_ATTRIBUTES",
        "WRITE_ATTRIBUTES",
        "READ_NAMED_ATTRS",
        "WRITE_NAMED_ATTRS",
        "READ_ACL",
        "WRITE_ACL",
        "WRITE_OWNER",
        "SYNCHRONIZE",
    ]

    flags = [
        "FILE_INHERIT",
        "DIRECTORY_INHERIT",
        "INHERIT_ONLY",
        "NO_PROPAGATE_INHERIT",
        "INHERITED"
    ]

    def __init__(self, hostname, path, **kwargs):
        self._path = path
        self._hostname = hostname
        self._version = kwargs.get('vers', 3)
        self._localpath = kwargs.get('localpath', '/mnt/testnfs')
        self._mounted = False
        self._user = kwargs.get('user')
        self._password = kwargs.get('password')
        self._ip = kwargs.get('ip')
        self._client_platform = kwargs.get('platform')

    def mount(self):
        raise NotImplementedError

    def umount(self):
        raise NotImplementedError

    def __enter__(self):
        self.mount()
        return self

    def __exit__(self, typ, value, traceback):
        self.umount()


class SSH_NFS(NFS):
    def acl_from_text(self, text):
        out = []
        for e in text.splitlines():
            entry = {
                "tag": None,
                "id": -1,
                "perms": {x: False for x in self.perms},
                "flags": {x: False for x in self.flags},
                "type": None
            }
            tp, flags, principal, perms = e.split(":")
            entry["type"] = "ALLOW" if tp == "A" else "DENY"
            if principal in ["OWNER@", "GROUP@", "EVERYONE@"]:
                entry["tag"] = principal.lower()
            else:
                entry["tag"] = "GROUP" if "g" in flags else "USER"
                entry["id"] = int(principal)

            for c in flags:
                if c == 'f':
                    entry['flags']['FILE_INHERIT'] = True
                elif c == 'd':
                    entry['flags']['DIRECTORY_INHERIT'] = True
                elif c == 'i':
                    entry['flags']['INHERIT_ONLY'] = True
                elif c == 'n':
                    entry['flags']['NO_PROPAGATE_INHERIT'] = True

            for c in perms:
                if c == 'r':
                    entry['perms']['READ_DATA'] = True
                elif c == 'w':
                    entry['perms']['WRITE_DATA'] = True
                elif c == 'a':
                    entry['perms']['APPEND_DATA'] = True
                elif c == 'D':
                    entry['perms']['DELETE_CHILD'] = True
                elif c == 'd':
                    entry['perms']['DELETE'] = True
                elif c == 'x':
                    entry['perms']['EXECUTE'] = True
                elif c == 't':
                    entry['perms']['READ_ATTRIBUTES'] = True
                elif c == 'T':
                    entry['perms']['WRITE_ATTRIBUTES'] = True
                elif c == 'n':
                    entry['perms']['READ_NAMED_ATTRS'] = True
                elif c == 'N':
                    entry['perms']['WRITE_NAMED_ATTRS'] = True
                elif c == 'c':
                    entry['perms']['READ_ACL'] = True
                elif c == 'C':
                    entry['perms']['WRITE_ACL'] = True
                elif c == 'o':
                    entry['perms']['WRITE_OWNER'] = True
                elif c == 'y':
                    entry['perms']['SYNCHRONIZE'] = True

            out.append(entry)

        return out

    def _ace_to_text(self, ace):
        out = "A:" if ace['type'] == 'ALLOW' else "D:"
        for k, v in ace['flags'].items():
            if not v:
                continue

            if k == 'FILE_INHERIT':
                out += "f"
            elif k == 'DIRECTORY_INHERIT':
                out += "d"
            elif k == 'INHERIT_ONLY':
                out += "i"
            elif k == 'NO_PROPAGATE_INHERIT':
                out += "n"

        if ace["tag"] in ["group@", "GROUP"]:
            out += "g"

        out += ":"
        if ace["tag"] in ("everyone@", "group@", "owner@"):
            out += ace["tag"].upper()
        else:
            out += str(ace["id"])

        out += ":"
        for k, v in ace['perms'].items():
            if not v:
                continue

            if k == 'READ_DATA':
                out += "r"
            elif k == 'WRITE_DATA':
                out += "w"
            elif k == 'APPEND_DATA':
                out += "a"
            elif k == 'DELETE_CHILD':
                out += "D"
            elif k == 'DELETE':
                out += "d"
            elif k == 'EXECUTE':
                out += "x"
            elif k == 'READ_ATTRIBUTES':
                out += "t"
            elif k == 'WRITE_ATTRIBUTES':
                out += "T"
            elif k == 'READ_NAMED_ATTRS':
                out += "n"
            elif k == 'WRITE_NAMED_ATTRS':
                out += "N"
            elif k == 'READ_ACL':
                out += "c"
            elif k == 'WRITE_ACL':
                out += "C"
            elif k == 'WRITE_OWNER':
                out += "o"
            elif k == 'SYNCHRONIZE':
                out += "y"

        return out

    def acl_to_text(self, acl):
        out = []
        for ace in acl:
            out.append(self._ace_to_text(ace))

        return ','.join(out)

    def getacl(self, path):
        if not self._mounted:
            raise RuntimeError("Export is not mounted")

        if path.startswith("/"):
            raise ValueError(f"{path}: absolute paths are not supported")

        getfacl = SSH_TEST(
            f"nfs4_getfacl {self._localpath}/{path}",
            self._user, self._password, self._ip
        )
        if getfacl['result'] == False:
            raise RuntimeError(getfacl['stderr'])

        return self.acl_from_text(getfacl['output'])

    def setacl(self, path, acl):
        if not self._mounted:
            raise RuntimeError("Export is not mounted")

        if path.startswith("/"):
            raise ValueError(f"{path}: absolute paths are not supported")

        acl_spec = self.acl_to_text(acl)

        setfacl = SSH_TEST(
            f"nfs4_setfacl {self._localpath}/{path} -s {acl_spec}",
            self._user, self._password, self._ip
        )

        if setfacl['result'] == False:
            raise RuntimeError(setfacl['stderr'])

    def mount(self):
        mkdir = SSH_TEST(f"mkdir {self._localpath}", self._user, self._password, self._ip)
        cmd = [
            'mount.nfs',
            '-o', f'vers={self._version}',
            f'{self._hostname}:{self._path}',
            self._localpath
        ]
        do_mount = SSH_TEST(" ".join(cmd), self._user, self._password, self._ip)
        if do_mount['result'] == False:
            raise RuntimeError(do_mount['output'])

        self._mounted = True

    def umount(self):
        if not self._mounted:
            return

        do_umount = SSH_TEST(f"umount -f {self._localpath}", self._user, self._password, self._ip)
        if do_umount['result'] == False:
            raise RuntimeError(do_umount['stderr'])

        self._mounted = False
