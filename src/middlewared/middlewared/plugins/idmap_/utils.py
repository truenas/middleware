import enum
import wbclient

from middlewared.service_exception import MatchNotFound


class IDType(enum.Enum):
    USER = "USER"
    GROUP = "GROUP"
    BOTH = "BOTH"

    def wbc_const(self):
        if self == IDType.USER:
            val = wbclient.WBC_ID_TYPE_UID
        elif self == IDType.GROUP:
            val = wbclient.WBC_ID_TYPE_GID
        else:
            val = wbclient.WBC_ID_TYPE_BOTH

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
        return self.ctx.uid_gid_objects_from_sids(uidsgids)

    def sid_to_uidgid_entry(self, sid):
        mapped = self.sids_to_users_and_groups([sid])
        if not mapped:
            raise MatchNotFound(sid)

        return mapped[sid]

    def uidgid_to_sid(self, data):
        mapped = self.users_and_groups_to_sids([data])
        if not mapped:
            raise MatchNotFound(str(data))

        return mapped[f'{data["id_type"]}:{data["id"]}']

    def all_domains(self):
        return self.ctx.all_domains()
