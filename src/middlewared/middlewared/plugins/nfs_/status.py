from middlewared.schema import accepts, Int, returns, Str
from middlewared.service import Service, private, filterable
from middlewared.utils import filter_list
from middlewared.service_exception import CallError
from contextlib import suppress

import yaml
import os


class NFSService(Service):

    @private
    def get_rmtab(self):
        """
        In future we can apply enhance based on socket status
        e.g ss -H -o state established '( sport = :nfs )'
        """
        entries = []
        with suppress(FileNotFoundError):
            with open("/var/lib/nfs/rmtab", "r") as f:
                for line in f:
                    ip, data = line.split(":", 1)
                    export, refcnt = line.rsplit(":", 1)
                    # for now we won't display the refcnt
                    entries.append({
                        "ip": ip,
                        "export": export,
                    })

        return entries

    @filterable
    def get_nfs3_clients(self, filters, options):
        """
        Read contents of rmtab. This information may not
        be accurate due to stale entries. This is ultimately
        a limitation of the NFSv3 protocol.
        """
        rmtab = self.get_rmtab()
        return filter_list(rmtab, filters, options)

    @private
    def get_nfs4_client_info(self, id):
        info = {}
        with suppress(FileNotFoundError):
            with open(f"/proc/fs/nfsd/clients/{id}/info", "r") as f:
                info = yaml.safe_load(f.read())

        return info

    @private
    def get_nfs4_client_states(self, id):
        states = []
        with suppress(FileNotFoundError):
            with open(f"/proc/fs/nfsd/clients/{id}/states", "r") as f:
                states = yaml.safe_load(f.read())

        # states file may be empty, which changes it to None type
        # return empty list in this case
        return states or []

    @filterable
    def get_nfs4_clients(self, filters, options):
        """
        Read information about NFSv4 clients from
        /proc/fs/nfsd/clients
        """
        clients = []
        with suppress(FileNotFoundError):
            for client in os.listdir("/proc/fs/nfsd/clients/"):
                entry = {
                    "id": client,
                    "info": self.get_nfs4_client_info(client),
                    "states": self.get_nfs4_client_states(client),
                }
                clients.append(entry)

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

    @private
    def close_client_state(self, client_id):
        """
        force the server to immediately revoke all state held by:
        `client_id`. This only applies to NFSv4. `client_id` is `id`
        returned in `get_nfs4_clients`.
        """
        with suppress(FileNotFoundError):
            with open(f"/proc/fs/nfsd/clients/{client_id}/ctl", "w") as f:
                f.write("expire\n")

    @private
    def get_threadpool_mode(self):
        with open("/sys/module/sunrpc/parameters/pool_mode", "r") as f:
            pool_mode = f.readline().strip()

        return pool_mode.upper()

    @private
    @accepts(Str("pool_mode", enum=["AUTO", "GLOBAL", "PERCPU", "PERNODE"]))
    def set_threadpool_mode(self, pool_mode):
        """
        Control how the NFS server code allocates CPUs to
        service thread pools.  Depending on how many NICs
        you have and where their interrupts are bound, this
        option will affect which CPUs will do NFS serving.
        Note: this parameter cannot be changed while the
        NFS server is running.

        auto        the server chooses an appropriate mode
                    automatically using heuristics
        global      a single global pool contains all CPUs
        percpu      one pool for each CPU
        pernode     one pool for each NUMA node (equivalent
                    to global on non-NUMA machines)
        """
        try:
            with open("/sys/module/sunrpc/parameters/pool_mode", "w") as f:
                f.write(pool_mode.lower())
        except OSError as e:
            raise CallError(
                "NFS service must be stopped before threadpool mode changes",
                errno=e.errno
            )
