import sys
import enum
import struct
import subprocess
from dataclasses import dataclass
from functions import SRVTarget, get_host_ip
from platform import system
from time import sleep


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
from samba import ntstatus
from samba import NTSTATUSError

libsmb_has_rename = 'rename' in dir(libsmb.Conn)


class Fsctl(enum.IntEnum):
    QUERY_FILE_REGIONS = 0x00090284



QFR_MAX_OUT = 64


class FileUsage(enum.IntEnum):
    VALID_CACHED_DATA = 0x00000001  # NTFS
    VALID_NONCACHED_DATA = 0x00000002  # REFS


@dataclass(frozen=True)
class FileRegionInfo:
    """ MS-FSCC 2.3.56.1 """
    offset: int
    length: int
    desired_usage: FileUsage = FileUsage.VALID_CACHED_DATA
    reserved: int = 0  # by protocol must be zero


@dataclass(frozen=True)
class FsctlQueryFileRegionsReply:
    """ MS-FSCC 2.3.56 """
    flags: int  # by protocol must be zero
    total_region_entry_count: int
    region_entry_count: int
    reserved: int  # by protocol must be zero
    region: FileRegionInfo


@dataclass()
class FsctlQueryFileRegionsRequest:
    """ MS-FSCC 2.3.55 """
    region_info: FileRegionInfo | None

    def __post_init__(self):
        self.fsctl = Fsctl.QUERY_FILE_REGIONS

    def pack(self):
        if self.region_info is None:
            return b''

        return struct.pack(
            '<qqII',
            self.region_info.offset,
            self.region_info.length,
            self.region_info.desired_usage,
            self.region_info.reserved
        )

    def unpack(self, buf):
        unpacked_resp = list(struct.unpack('<IIII', buf[0:16]))
        unpacked_resp.append(FileRegionInfo(*struct.unpack('<qqII', buf[16:])))
        return FsctlQueryFileRegionsReply(*unpacked_resp)


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


class SMBEncryption(enum.IntEnum):
    """ Specify SMB encryption level for client. Used during negotiate """
    DEFAULT = credentials.SMB_ENCRYPTION_DEFAULT
    DESIRED = credentials.SMB_ENCRYPTION_DESIRED
    REQUIRED = credentials.SMB_ENCRYPTION_REQUIRED


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
        host = kwargs.get("host", get_host_ip(SRVTarget.DEFAULT))
        share = kwargs.get("share")
        encryption = SMBEncryption[kwargs.get("encryption", "DEFAULT")]
        username = kwargs.get("username")
        domain = kwargs.get("domain")
        password = kwargs.get("password")
        smb1 = kwargs.get("smb1", False)

        self._lp = s3param.get_context()
        self._lp.load_default()
        self._cred = credentials.Credentials()
        self._cred.guess(self._lp)
        self._cred.set_smb_encryption(encryption)

        if username is not None:
            self._cred.set_username(username)
        if password is not None:
            self._cred.set_password(password)
        if domain is not None:
            self._cred.set_domain(domain)

        self._host = host
        self._share = share
        self._smb1 = smb1
        self._username = username
        self._password = password
        self._domain = domain
        try:
            self._connection = libsmb.Conn(
                host,
                share,
                self._lp,
                self._cred,
                force_smb1=smb1,
            )
        except NTSTATUSError as nterr:
            if nterr.args[0] != ntstatus.NT_STATUS_CONNECTION_REFUSED:
                raise nterr

            # Samba service may still be in process of reloading. Sleep and retry
            sleep(5)

            self._connection = libsmb.Conn(
                host,
                share,
                self._lp,
                self._cred,
                force_smb1=smb1,
            )

    def get_smb_encryption(self):
        return SMBEncryption(self._cred.get_smb_encryption()).name

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
        host = kwargs.get("host", get_host_ip(SRVTarget.DEFAULT))
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
        host = kwargs.get("host", get_host_ip(SRVTarget.DEFAULT))
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
        host = kwargs.get("host", get_host_ip(SRVTarget.DEFAULT))
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

    def set_sd(self, idx, secdesc, security_info):
        self._connection.set_sd(self._open_files[idx]["fh"], secdesc, security_info)

    def get_sd(self, idx, security_info):
        return self._connection.get_sd(self._open_files[idx]["fh"], security_info)

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

    def fsctl(self, idx, fsctl_request, max_out):
        resp = self._connection.fsctl(
            self._open_files[idx]["fh"], fsctl_request.fsctl, fsctl_request.pack(), max_out
        )

        return fsctl_request.unpack(resp)
