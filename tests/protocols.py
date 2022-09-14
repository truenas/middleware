import sys
import enum
import subprocess
from functions import SSH_TEST
from platform import system

# sys.real_prefix only found in old virtualenv
# if detected set local site-packages to use for samba
# In recent virtual version sys.base_prefix is to be use.
if getattr(sys, "real_prefix", None):
    major_v = sys.version_info.major
    minor_v = sys.version_info.minor
    if system() == 'Linux':
        sys.path.append(f'{sys.real_prefix}/lib/python{major_v}/dist-packages')
    else:
        sys.path.append(f'{sys.real_prefix}/lib/python{major_v}.{minor_v}/site-packages')
elif sys.prefix != sys.base_prefix:
    major_v = sys.version_info.major
    minor_v = sys.version_info.minor
    if system() == 'Linux':
        sys.path.append(f'{sys.base_prefix}/lib/python{major_v}/dist-packages')
    else:
        sys.path.append(f'{sys.base_prefix}/lib/python{major_v}.{minor_v}/site-packages')

from samba.samba3 import libsmb_samba_internal as libsmb
from samba.dcerpc import security
from samba.samba3 import param as s3param
from samba import credentials
from samba import NTSTATUSError

libsmb_has_rename = 'rename' in dir(libsmb.Conn)


class ACLControl(enum.IntFlag):
    SEC_DESC_OWNER_DEFAULTED        = 0x0001
    SEC_DESC_GROUP_DEFAULTED        = 0x0002
    SEC_DESC_DACL_PRESENT           = 0x0004
    SEC_DESC_DACL_DEFAULTED         = 0x0008
    SEC_DESC_SACL_PRESENT           = 0x0010
    SEC_DESC_SACL_DEFAULTED         = 0x0020
    SEC_DESC_DACL_TRUSTED           = 0x0040
    SEC_DESC_SERVER_SECURITY        = 0x0080
    SEC_DESC_DACL_AUTO_INHERIT_REQ  = 0x0100
    SEC_DESC_SACL_AUTO_INHERIT_REQ  = 0x0200
    SEC_DESC_DACL_AUTO_INHERITED    = 0x0400
    SEC_DESC_SACL_AUTO_INHERITED    = 0x0800
    SEC_DESC_DACL_PROTECTED         = 0x1000
    SEC_DESC_SACL_PROTECTED         = 0x2000
    SEC_DESC_RM_CONTROL_VALID       = 0x4000
    SEC_DESC_SELF_RELATIVE          = 0x8000


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
        self._username = username
        self._password = password
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

    def rename(self, src, dst):
        if libsmb_has_rename:
            return self._connection.rename(src, dst)

        cmd = [
            "smbclient", f"//{self._host}/{self._share}",
            "-U", f"{self._username}%{self._password}",
        ]

        if self._smb1:
            cmd.extend(["-m", "NT1"])

        cmd.extend(["-c", f'rename {src} {dst}'])
        cl = subprocess.run(cmd, capture_output=True)
        if cl.returncode != 0:
            raise RuntimeError(cl.stdout.decode())

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

    def get_sd(self, path):
        def get_offset_by_key(data, key):
            for idx, entry in enumerate(data):
                if entry.startswith(key):
                    return data[idx:]

            raise ValueError(f'Failed to parse ACL: {data}')

        cmd = [
            "smbcacls", f"//{self._host}/{self._share}",
            "-U", f"{self._username}%{self._password}",
            "--numeric"
        ]

        if self._smb1:
            cmd.extend(["-m", "NT1"])

        cmd.append(path)

        cl = subprocess.run(cmd, capture_output=True)
        if cl.returncode != 0:
            raise RuntimeError(cl.stdout.decode() or cl.stderr.decode())

        output = get_offset_by_key(cl.stdout.decode().splitlines(), 'REVISION')
        revision = int(output[0].split(':')[1])
        control = {"raw": output[1].split(':')[1]}
        control['parsed'] = [x.name for x in ACLControl if int(control['raw'], 16) & x]

        sd = {
            "revision": revision,
            "control": control,
            "owner": output[2].split(':')[1],
            "group": output[3].split(':')[1],
            "acl": []
        }
        for l in get_offset_by_key(output, 'ACL'):
            entry, flags, access_mask = l.split("/")
            prefix, trustee, ace_type = entry.split(":")

            sd['acl'].append({
                "trustee": trustee,
                "type": int(ace_type),
                "access_mask": int(access_mask, 16),
                "flags": int(flags, 16),
            })

        return sd

    def inherit_acl(self, path, action):
        cmd = [
            "smbcacls", f"//{self._host}/{self._share}",
            "-U", f"{self._username}%{self._password}"
        ]

        if action in ["ALLOW", "REMOVE", "COPY"]:
            cmd.extend(["-I", action.lower()])

        elif action == "PROPAGATE":
            cmd.append('--propagate-iheritance')

        else:
            raise ValueError(f"{action}: invalid action")

        if self._smb1:
            cmd.extend(["-m", "NT1"])

        cmd.append(path)

        cl = subprocess.run(cmd, capture_output=True)
        if cl.returncode != 0:
            raise RuntimeError(cl.stdout.decode() or cl.stderr.decode())


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

    def validate(self, path):
        if not self._mounted:
            raise RuntimeError("Export is not mounted")

        if path.startswith("/"):
            raise ValueError(f"{path}: absolute paths are not supported")

        return

    def mkdir(self, path):
        mkdir = SSH_TEST(
            f"mkdir {self._localpath}/{path}",
            self._user, self._password, self._ip
        )
        if mkdir['result'] == False:
            raise RuntimeError(mkdir['stderr'])

    def rmdir(self, path):
        rmdir = SSH_TEST(
            f"rmdir {self._localpath}/{path}",
            self._user, self._password, self._ip
        )
        if rmdir['result'] == False:
            raise RuntimeError(rmdir['stderr'])

    def ls(self, path):
        ls = SSH_TEST(
            f"ls {self._localpath}/{path}",
            self._user, self._password, self._ip
        )
        if ls['result'] == False:
            raise RuntimeError(ls['stderr'])

        return ls['output']

    def rename(self, src, dst): 
        mv = SSH_TEST(
            f"mv {self._localpath}/{path} {self._localpath}/{path}",
            self._user, self._password, self._ip
        )
        if mv['result'] == False:
            raise RuntimeError(mv['stderr'])

    def unlink(self, path):
        rm = SSH_TEST(
            f"rm {self._localpath}/{path}",
            self._user, self._password, self._ip
        )
        if rm['result'] == False:
            raise RuntimeError(rm['stderr'])

    def getacl(self, path):
        self.validate(path)
        getfacl = SSH_TEST(
            f"nfs4_getfacl {self._localpath}/{path}",
            self._user, self._password, self._ip
        )
        if getfacl['result'] == False:
            raise RuntimeError(getfacl['stderr'])

        return self.acl_from_text(getfacl['output'])

    def setacl(self, path, acl):
        self.validate(path)

        acl_spec = self.acl_to_text(acl)
        setfacl = SSH_TEST(
            f"nfs4_setfacl {self._localpath}/{path} -s {acl_spec}",
            self._user, self._password, self._ip
        )

        if setfacl['result'] == False:
            raise RuntimeError(setfacl['stderr'])

    def getxattr(self, path, xattr_name):
        self.validate(path)

        cmd = ['getfattr', '--only-values', '-m', xattr_name, f'{self._localpath}/{path}']
        getxattr = SSH_TEST(' '.join(cmd), self._user, self._password, self._ip)
        if getxattr['result'] == False:
            raise RuntimeError(getxattr['stderr'])

        return getxattr['output']

    def setxattr(self, path, xattr_name, value):
        self.validate(path)

        cmd = ['setfattr', '-n', xattr_name, '-v', value, f'{self._localpath}/{path}']
        setxattr = SSH_TEST(' '.join(cmd), self._user, self._password, self._ip)
        if setxattr['result'] == False:
            raise RuntimeError(setxattr['stderr'])

    def create(self, path, is_dir=False):
        self.validate(path)
        create = SSH_TEST(
            f'{"mkdir" if is_dir else "touch"} {self._localpath}/{path}',
            self._user, self._password, self._ip
        )
        if create['result'] == False:
            raise RuntimeError(create['stderr'])

    def server_side_copy(self, path1, path2):
        """
        Currently this is a hack and so writes a default payload to fd1 and then
        does copy_file_range() to duplicate to fd2
        """
        self.validate(path1)
        self.validate(path2)

        python_script = [
            "import os",
            f"file1 = open('{self._localpath}/{path1}', 'w')",
            "file1.write('canary')",
            "file1.flush()",
            "os.fsync(file1.fileno())",
            f"srcfd = os.open('{self._localpath}/{path1}', os.O_CREAT | os.O_RDWR)",
            f"dstfd = os.open('{self._localpath}/{path2}', os.O_CREAT | os.O_RDWR)",
            "written = os.copy_file_range(srcfd, dstfd, len('canary'))",
            "assert written == len('canary')"
        ]
        cmd = ['python3', '-c']
        cmd.append(f'"{";".join(python_script)}"')

        rv = SSH_TEST(' '.join(cmd), self._user, self._password, self._ip)
        if rv['result'] == False:
            raise RuntimeError(rv['stderr'])

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
