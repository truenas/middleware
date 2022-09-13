import enum
import errno
import wbclient

from middlewared.service_exception import MatchNotFound


WBCErr = {
    wbclient.WBC_ERR_SUCCESS: None,
    wbclient.WBC_ERR_NOT_IMPLEMENTED: errno.ENOSYS,
    wbclient.WBC_ERR_UNKNOWN_FAILURE: errno.EFAULT,
    wbclient.WBC_ERR_NO_MEMORY: errno.ENOMEM,
    wbclient.WBC_ERR_INVALID_SID: errno.EINVAL,
    wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE: errno.ENOTCONN,
    wbclient.WBC_ERR_DOMAIN_NOT_FOUND: errno.ENOENT,
    wbclient.WBC_ERR_INVALID_RESPONSE: errno.EBADMSG,
    wbclient.WBC_ERR_NSS_ERROR: errno.EFAULT,
    wbclient.WBC_ERR_AUTH_ERROR: errno.EPERM,
    wbclient.WBC_ERR_UNKNOWN_USER: errno.ENOENT,
    wbclient.WBC_ERR_UNKNOWN_GROUP: errno.ENOENT,
    wbclient.WBC_ERR_PWD_CHANGE_FAILED: errno.EFAULT
}


class IDType(enum.Enum):
    USER = "USER"
    GROUP = "GROUP"
    BOTH = "BOTH"

    def wbc_const(self):
        if self == IDType.USER:
            val = wbclient.ID_TYPE_UID
        elif self == IDType.GROUP:
            val = wbclient.ID_TYPE_GID
        else:
            val = wbclient.ID_TYPE_BOTH

        return val

    def wbc_str(self):
        if self == IDType.USER:
            val = "UID"
        elif self == IDType.GROUP:
            val = "GID"
        else:
            val = "BOTH"

        return val


class WBClient:
    def __init__(self, **kwargs):
        self.ctx = wbclient.Ctx()
        self.dom = {}

    def init_domain(self, name='$thisdom'):
        domain = self.dom.get(name)
        if domain:
            return domain

        if name == '$thisdom':
            domain = self.ctx.domain()
        else:
            domain = self.ctx.domain(name)

        self.dom[name] = domain
        return domain

    def ping_dc(self, name='$thisdom'):
        dom = self.init_domain(name)
        return dom.ping_dc()

    def check_trust(self, name='$thisdom'):
        dom = self.init_domain(name)
        return dom.check_secret()

    def domain_info(self, name='$thisdom'):
        dom = self.init_domain(name)
        return dom.domain_info()

    def users(self, name='$thisdom'):
        dom = self.init_domain(name)
        return dom.users()

    def groups(self, name='$thisdom'):
        dom = self.init_domain(name)
        return dom.groups()

    def sids_to_users_and_groups(self, sidlist):
        return self.ctx.uid_gid_objects_from_sids(sidlist)

    def users_and_groups_to_sids(self, uidgids):
        return self.ctx.uid_gid_objects_from_unix_ids(uidgids)

    def sid_to_uidgid_entry(self, sid):
        mapped = self.sids_to_users_and_groups([sid])['mapped']
        if not mapped:
            raise MatchNotFound(sid)

        return mapped[sid]

    def name_to_uidgid_entry(self, name):
        try:
            entry = self.ctx.uid_gid_object_from_name(name)
        except wbclient.WBCError as e:
            if e.error_code == wbclient.WBC_ERR_DOMAIN_NOT_FOUND:
                raise MatchNotFound

            raise

        return entry

    def uidgid_to_sid(self, data):
        mapped = self.users_and_groups_to_sids([data])['mapped']
        if not mapped:
            raise MatchNotFound(str(data))

        return mapped[f'{data["id_type"]}:{data["id"]}']

    def all_domains(self):
        return self.ctx.all_domains()
