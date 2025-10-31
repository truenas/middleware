import errno

from itertools import batched

import wbclient

from .idmap_constants import IDType, MAX_REQUEST_LENGTH
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


class WBClient:
    def __init__(self, **kwargs):
        self.ctx = wbclient.Ctx()
        self.dom = {}
        self.separator = self.ctx.separator.decode()

    def _pyuidgid_to_dict(self, entry):
        """ convert python wbclient uidgid object to dictionary """
        return {
            'id_type': IDType(entry.id_type).name,
            'id': entry.id,
            'name': f'{entry.domain}{self.separator}{entry.name}' if entry.name else None,
            'sid': entry.sid
        }

    def _as_dict(self, results, convert_unmapped=False):
        for entry in list(results['mapped'].keys()):
            new = self._pyuidgid_to_dict(results['mapped'][entry])
            if new['id_type'] == IDType.BOTH.name:
                if results['mapped'][entry].sid_type['parsed'] in ('SID_DOM_GROUP', 'SID_ALIAS'):
                    new['id_type'] = IDType.GROUP.name
                else:
                    new['id_type'] = IDType.USER.name

            results['mapped'][entry] = new

        # The unmapped entry value may be uidgid type or simply SID string
        # in latter case we shouldn't try to convert
        if convert_unmapped:
            for entry in list(results['unmapped'].keys()):
                new = self._pyuidgid_to_dict(results['unmapped'][entry])
                results['unmapped'][entry] = new

        return results

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
        """ perform wbinfo --ping-dc """
        dom = self.init_domain(name)
        return dom.ping_dc()

    def check_trust(self, name='$thisdom'):
        """ perform wbinfo -t """
        dom = self.init_domain(name)
        return dom.check_secret()

    def domain_info(self, name='$thisdom'):
        """ perform wbinfo --domain-info """
        dom = self.init_domain(name)
        return dom.domain_info()

    def _batch_request(self, request_fn, list_in):
        output = {'mapped': {}, 'unmapped': {}}
        for chunk in batched(list_in, MAX_REQUEST_LENGTH):
            results = request_fn(list(chunk))
            output['mapped'] |= results['mapped']
            output['unmapped'] |= results['unmapped']

        return output

    def sids_to_idmap_entries(self, sidlist):
        """
        Bulk conversion of SIDs to idmap entries

        Returns dictionary:
        {"mapped": {}, "unmapped": {}

        `mapped` contains entries keyed by SID

        sid: {
            'id': uid or gid,
            'id_type': string ("USER", "GROUP", "BOTH"),
            'name': string,
            'sid': sid string
        }

        `unmapped` contains enries keyed by SID as well
        but they only map to the sid itself. This is simply
        to facilitate faster lookups of failures.
        """
        data = self._batch_request(
            self.ctx.uid_gid_objects_from_sids,
            sidlist
        )
        return self._as_dict(data)

    def users_and_groups_to_idmap_entries(self, uidgids):
        """
        Bulk conversion of list of dictionaries containing the
        following keys:

        id_type : string. possible values "USER", "GROUP"
        id : integer

        Returns dictionary:
        {"mapped": {}, "unmapped": {}

        `mapped` contains entries keyed by string with either
        UID:<xid>, or GID:<xid>

        'UID:1000': {
            'id': 1000,
            'id_type': 'USER',
            'name': 'bob',
            'sid': sid string
        }
        """
        payload = [{
            'id_type': IDType[entry["id_type"]].wbc_str(),
            'id': entry['id']
        } for entry in uidgids]

        data = self._batch_request(
            self.ctx.uid_gid_objects_from_unix_ids,
            payload
        )
        return self._as_dict(data, True)

    def sid_to_idmap_entry(self, sid):
        mapped = self.sids_to_users_and_groups([sid])['mapped']
        if not mapped:
            raise MatchNotFound(sid)

        return mapped[sid]

    def name_to_idmap_entry(self, name):
        try:
            entry = self.ctx.uid_gid_object_from_name(name)
        except wbclient.WBCError as e:
            if e.error_code == wbclient.WBC_ERR_DOMAIN_NOT_FOUND:
                raise MatchNotFound

            raise

        return self._pyuidgid_to_dict(entry)

    def uidgid_to_idmap_entry(self, data):
        """
        Convert payload specified in `data` to a idmap entry. Wraps around
        users_and_groups_to_idmap_entries. See above.

        Raises:
            MatchNotFound
        """
        mapped = self.users_and_groups_to_idmap_entries([data])['mapped']
        if not mapped:
            raise MatchNotFound(str(data))

        return mapped[f'{IDType[data["id_type"]].wbc_str()}:{data["id"]}']

    def all_domains(self):
        return self.ctx.all_domains()
