import errno
import enum
import json
import subprocess

from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import private, CallError, Service
from middlewared.plugins.smb import SMBCmd


class ACLType(enum.Enum):
    SMB = "SMB"
    NFSV4 = "NFSv4"


class ACLFlags(enum.Enum):
    FI = ("FILE_INHERIT", "OBJECT_INHERIT")
    DI = ("DIRECTORY_INHERIT", "CONTAINER_INHERIT")
    NI = ("NO_PROPAGATE_INHERIT", "NO_PROPAGATE_INHERIT")
    IO = ("INHERIT_ONLY", "INHERIT_ONLY")
    ID = ("INHERITED", "INHERITED")

    def convert(aclt, in_flags):
        acl = ACLType[aclt]
        rv = {}
        if acl == ACLType.SMB:
            for f in ACLFlags:
                parm = in_flags.get(f.value[1])
                rv.update({f.value[0]: True if parm else False})
        else:
            for f in ACLFlags:
                parm = in_flags.get(f.value[0])
                rv.update({f.value[1]: True if parm else False})

        return rv


class ACLPerms(enum.Enum):
    RD = ("READ_DATA", "READ")
    WD = ("WRITE_DATA", "WRITE")
    EX = ("EXECUTE", "EXECUTE")
    DE = ("DELETE", "DELETE_CHILD")
    DC = ("DELETE_CHILD", "DELETE")
    AD = ("APPEND_DATA", "APPEND_DATA")
    RA = ("READ_ATTRIBUTES", "READ_ATTRIBUTES")
    WA = ("WRITE_ATTRIBUTES", "WRITE_ATTRIBUTES")
    RE = ("READ_NAMED_ATTRS", "READ_EA")
    WE = ("WRITE_NAMED_ATTRS", "WRITE_EA")
    RC = ("READ_ACL", "READ_CONTROL")
    WC = ("WRITE_ACL", "WRITE_DAC")
    WO = ("WRITE_OWNER", "WRITE_OWNER")
    SY = ("SYNCHRONIZE", "SYNCHRONIZE")

    def convert(aclt, in_perms):
        acl = ACLType[aclt]
        rv = {}
        if acl == ACLType.SMB:
            for f in ACLPerms:
                parm = in_perms.get(f.value[1])
                rv.update({f.value[0]: True if parm else False})
        else:
            for f in ACLPerms:
                parm = in_perms.get(f.value[0])
                rv.update({f.value[1]: True if parm else False})

        return rv


class SMBService(Service):

    class Config:
        service = 'cifs'
        service_verb = 'restart'

    @accepts(
        Dict(
            'get_remote_acl',
            Str('server', required=True),
            Str('share', required=True),
            Str('path', default='\\'),
            Str('username', required=True),
            Str('password', required=True),
            Dict(
                'options',
                Bool('use_kerberos', default=False),
                Str('output_format', enum=['SMB', 'LOCAL'], default='SMB'),
            )
        )
    )
    def get_remote_acl(self, data):
        """
        Retrieves an ACL from a remote SMB server.

        `server` IP Address or hostname of the remote server

        `share` Share name

        `path` path on the remote SMB server. Use "\" to separate path components

        `username` username to use for authentication

        `password` password to use for authentication

        `use_kerberos` use credentials to get a kerberos ticket for authentication.
        AD only.

        `output_format` format for resulting ACL data. Choices are either 'SMB',
        which will present the information as a Windows SD or 'LOCAL', which formats
        the ACL information according local filesystem of the TrueNAS server.
        """
        if data['options']['use_kerberos']:
            raise CallError("kerberos authentication for this function is not "
                            "currently supported.", errno.EOPNOTSUP)

        sc = subprocess.run([
            SMBCmd.SMBCACLS.value,
            f'//{data["server"]}/{data["share"]}',
            data['path'], '-j', '-U', data['username']],
            capture_output=True,
            input=data['password'].encode()
        )
        if sc.returncode != 0:
            raise CallError("Failed to retrieve remote SMB server ACL: "
                            f"{sc.stderr.decode().strip()}")
        smb_sd = json.loads(sc.stdout.decode().splitlines()[1])
        if data['options']['output_format'] == 'SMB':
            return {"acl_type": "SMB", "acl_data": smb_sd}

    @private
    async def smb_to_nfsv4(self, sd, ignore_errors=False):
        acl_out = {"uid": None, "gid": None, "acl": []}
        for x in sd['dacl']:
            entry = {'tag': None, 'id': None, 'type': None, 'perms': {}, 'flags': {}}
            entry['perms'] = ACLPerms.convert('SMB', x['access_mask']['special'])
            entry['flags'] = ACLFlags.convert('SMB', x['flags'])
            entry['type'] = "ALLOW" if x['type'] == "ALLOWED" else "DENY"
            if x['trustee']['sid'] == "S-1-3-0":
                entry['tag'] = "owner@"
            elif x['trustee']['sid'] == "S-1-3-1":
                entry['tag'] = "group@"
            elif x['trustee']['sid'] == "S-1-1-0":
                entry['tag'] = "everyone@"
            else:
                trustee = await self.middleware.call('idmap.sid_to_name',
                                                     x['trustee']['sid'])
                if trustee is None:
                    if not ignore_errors:
                        raise CallError(f"Failed to convert SID [{x['trustee']['sid']}] "
                                        "to ID")
                    else:
                        self.logger.debug(f"Failed to convert SID [{x['trustee']['sid']}] "
                                          f"to ID. Dropping entry from ACL: {x}.")
                        continue

                entry['tag'] = "USER" if trustee['id_type'] == "USER" else "GROUP"
                entry['id'] = trustee['id']

            acl_out.append(entry)

        return {"acl_type": "NFSV4", "acl_data": acl_out}

    @private
    async def convert_acl(self, acl_type, data):
        aclt = ACLType[acl_type]
        if aclt == ACLType.SMB:
            return await self.smb_to_nfsv4(data)
