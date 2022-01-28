from middlewared.schema import accepts, Int, returns
from middlewared.service import Service, private, filterable
from middlewared.utils import filter_list

import yaml
import os


class NFSService(Service):

    @private
    def get_rmtab(self):
        entries = []
        try:
            with open("/var/lib/nfs/rmtab", "r") as f:
               for line in f:
                   ip, data  = line.split(":", 1)
                   export, refcnt = line.rsplit(":", 1)
                   # for now we won't display the refcnt
                   entries.append({
                       "ip": ip,
                       "export": export,
                   })
        except FileNotFoundError:
            self.logger.debug("Failed to read rmtab", exc_info=True)

        return entries

    @private
    @filterable
    def get_nfs3_clients(self, filters, options):
        # can apply additional filtering here based on socket status:
        # e.g ss -H -o state established '( sport = :nfs )'
        rmtab = self.get_rmtab()
        return filter_list(rmtab, filters, options)

    @private
    def get_nfs4_client_info(self, id):
        info = {}
        try:
            with open(f"/proc/fs/nfsd/clients/{id}/info", "r") as f:
                info = yaml.safe_load(f.read())
        except FileNotFoundError:
            pass

        return info

    @private
    def get_nfs4_client_states(self, id):
        states = []
        try:
            with open(f"/proc/fs/nfsd/clients/{id}/states", "r") as f:
                states = yaml.safe_load(f.read())
        except FileNotFoundError:
            pass

        # states file may be empty, which changes it to None type
        # return empty list in this case
        return states or []

    @private
    @filterable
    def get_nfs4_clients(self, filters, options):
        clients = []
        try:
            for client in os.listdir("/proc/fs/nfsd/clients/"):
                entry = {
                    "id": client,
                    "info": self.get_nfs4_client_info(client),
                    "states": self.get_nfs4_client_states(client),
                }
                clients.append(entry)

        except FileNotFoundError
            pass

        return filter_list(clients, filters, options)

    @accepts()
    @returns(Int('number_of_clients'))
    def client_count(self):
        """
        Return currently connected clients count.
        Count may not be accurate if NFSv3 protocol is in use
        due to potentially stale rmtab entries.
        """

        cnt = 0
        for op in (self.get_nfs3_clients, self.get_nfs4_clients):
            cnt += op([], {"count": True})

        return cnt
