import errno
import enum
import json
import subprocess

from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import private, CallError, Service
from middlewared.plugins.smb import SMBCmd


class ACLType(enum.Enum):
    SMB = "SMB"
    NFSV4 = "NFSV4"


class ACLPrincipal(enum.Enum):
    OWNER = ("owner@", "CREATOR-OWNER", "S-1-3-0")
    GROUP = ("group@", "CREATOR-GROUP", "S-1-3-1")
    EVERYONE = ("everyone@", "EVERYONE", "S-1-1-0")

    def list_txt(acl_type):
        aclt = ACLType[acl_type]
        if aclt == ACLType.SMB:
            return [x.value[1] for x in ACLPrincipal]

        elif aclt == ACLType.NFSV4:
            return [x.value[0] for x in ACLPrincipal]

    def sids():
        return [x.value[2] for x in ACLPrincipal]

    def from_sid(sid):
        for x in ACLPrincipal:
            if sid == x.value[2]:
                return x

        return None

    def from_nfsv4(principal):
        for x in ACLPrincipal:
            if principal == x.value[0]:
                return x

        return None

    def to_sid(self):
        return self.value[2]

    def to_smb(self):
        return self.value[1]

    def to_nfsv4(self):
        return self.value[0]


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
    RD = (("READ_DATA", 0x00000008), ("READ", 0x00000001))
    WD = (("WRITE_DATA", 0x00000010), ("WRITE", 0x00000002))
    EX = (("EXECUTE", 0x0001), ("EXECUTE", 0x00000020))
    DE = (("DELETE", 0x00000100), ("DELETE", 0x00010000))
    WC = (("WRITE_ACL", 0x00002000), ("WRITE_DAC", 0x00040000))
    WO = (("WRITE_OWNER", 0x00004000), ("WRITE_OWNER", 0x00080000))
    AD = (("APPEND_DATA", 0x00000020), ("APPEND_DATA", 0x00000004))
    RA = (("READ_ATTRIBUTES", 0x00000200), ("READ_ATTRIBUTES", 0x00000080))
    WA = (("WRITE_ATTRIBUTES", 0x00000400), ("WRITE_ATTRIBUTES", 0x00000100))
    RE = (("READ_NAMED_ATTRS", 0x00000040), ("READ_EA", 0x00000008))
    WE = (("WRITE_NAMED_ATTRS", 0x00000080), ("WRITE_EA", 0x00000010))
    DC = (("DELETE_CHILD", 0x00000800), ("DELETE_CHILD", 0x00000040))
    RC = (("READ_ACL", 0x00001000), ("READ_CONTROL", 0x00020000))
    SY = (("SYNCHRONIZE", 0x00008000), ("SYNCHRONIZE", 0x00100000))

    def convert(aclt, in_perms):
        acl = ACLType[aclt]
        rv = {}
        if acl == ACLType.SMB:
            for f in ACLPerms:
                parm = in_perms.get(f.value[1][0])
                rv.update({f.value[0][0]: True if parm else False})
        else:
            for f in ACLPerms:
                parm = in_perms.get(f.value[0][0])
                rv.update({f.value[1][0]: True if parm else False})

        return rv

    def to_standard(in_perms):
        defaults = {x.value[1][0]: False for x in ACLPerms}
        std_perms = {
            "READ": defaults.copy(),
            "CHANGE": defaults.copy(),
            "FULL": {x.value[1][0]: True for x in ACLPerms}
        }
        std_perms["READ"].update({
            "READ": True,
            "EXECUTE": True
        })
        std_perms["CHANGE"].update({
            "READ": True,
            "EXECUTE": True,
            "DELETE": True,
            "WRITE": True
        })
        for k, v in std_perms.items():
            if v == in_perms:
                return k

        return ""

    def to_hex(aclt, in_perms):
        acl = ACLType[aclt]
        rv = 0
        if acl == ACLType.SMB:
            for f in ACLPerms:
                if in_perms.get(f.value[1][0]):
                    rv = rv | f.value[1][1]

        return f"0x{hex(rv)[2:].zfill(8)}"


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

            if x['trustee']['sid'] in ACLPrincipal.sids():
                aclp = ACLPrincipal.from_sid(x['trustee']['sid'])
                entry['tag'] = aclp.to_nfsv4
            else:
                trustee = await self.middleware.call('idmap.sid_to_unixid',
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
    async def get_trustee(self, unixid, id_type):
        out = {"sid": None, "name": None}
        if unixid is None:
            aclp = ACLPrincipal.from_nfsv4(id_type)
            out['sid'] = aclp.to_sid()
            out['name'] = aclp.to_smb()
        else:
            out['sid'] = await self.middleware.call('idmap.unixid_to_sid', {"id": unixid, "id_type": id_type})
            if out['sid'] is not None:
                out['name'] = await self.middleware.call('idmap.sid_to_name', out['sid'])

        return out

    @private
    async def nfsv4_to_smb(self, nfs4acl, ignore_errors=False):
        inherited_present = False
        sd_out = {
            "revision": 1,
            "owner": {"sid": None, "name": None},
            "group": {"sid": None, "name": None},
            "dacl": [],
            "control": {
                "Self Relative": True,
                "RM Control Valid": False,
                "SACL Protected": False,
                "DACL Protected": False,
                "SACL Auto Inherited": False,
                "DACL Auto Inherited": False,
                "SACL Inheritance Required": False,
                "DACL Inheritance Required": False,
                "Server Security": False,
                "DACL Trusted": False,
                "SACL Defaulted": False,
                "SACL Present": False,
                "DACL Defaulted": False,
                "DACL Present": True,
                "Group Defaulted": False,
                "Owner Defaulted": False,
            }
        }
        for x in [("owner", "uid", "user"), ("group", "gid", "group")]:
            sd_out[x[0]] = await self.get_trustee(nfs4acl[x[1]], x[2].upper())

        for ace in nfs4acl["acl"]:
            entry = {
                "trustee": {"sid": None, "name": None},
                "type": None,
                "access_mask": {"hex": "", "standard": "", "special": {}, "unknown": "0x00000000"},
                "flags": {},
            }
            entry["trustee"] = await self.get_trustee(ace["id"], ace["tag"])
            must_special_convert = entry["trustee"]["sid"] in ["S-1-3-0", "S-1-3-1"]
            entry["type"] = "ALLOWED" if ace["type"] == "ALLOW" else "DENIED"
            entry["access_mask"]["special"] = ACLPerms.convert("NFSV4", ace["perms"])

            if entry["type"] == "ALLOWED":
                entry["access_mask"]["special"]["SYNCHRONIZE"] = True

            entry["access_mask"]["standard"] = ACLPerms.to_standard(entry["access_mask"]["special"])
            entry["access_mask"]["hex"] = ACLPerms.to_hex("SMB", entry["access_mask"]["special"])
            entry["flags"] = ACLFlags.convert("NFSV4", ace["flags"])

            if entry["flags"]["INHERITED"]:
                inherited_present = True

            if must_special_convert:
                entry["flags"]["INHERIT_ONLY"] = True
                dup_entry = entry.copy()
                dup_entry["trustee"] = sd_out["owner"].copy() if entry["trustee"]["sid"] == "S-1-3-0" else sd_out["group"].copy()
                dup_entry["flags"].update({
                    "OBJECT_INHERIT": False,
                    "CONTAINER_INHERIT": False,
                    "INHERIT_ONLY": False,
                    "NO_PROPAGATE_INHERIT": False
                })
                sd_out['dacl'].append(entry)
                sd_out['dacl'].append(dup_entry)
            else:
                sd_out['dacl'].append(entry)

        if not inherited_present:
            sd_out['control']['DACL Protected'] = True

        return {"acl_type": "SMB", "acl_data": sd_out}

    @private
    async def convert_acl(self, acl_type, data):
        aclt = ACLType[acl_type]
        if aclt == ACLType.SMB:
            return await self.smb_to_nfsv4(data)
        else:
            return await self.nfsv4_to_smb(data)
