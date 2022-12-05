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
