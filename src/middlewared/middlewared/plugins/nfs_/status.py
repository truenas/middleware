from middlewared.plugins.nfs import NFSServicePathInfo
from middlewared.schema import accepts, Int, returns, Str, Dict
from middlewared.service import Service, private, filterable, filterable_returns
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
            with open(os.path.join(NFSServicePathInfo.STATEDIR.path(), "rmtab"), "r") as f:
                for line in f:
                    ip, data = line.split(":", 1)
                    export, refcnt = line.rsplit(":", 1)
                    # for now we won't display the refcnt
                    entries.append({
                        "ip": ip,
                        "export": export,
                    })

        return entries

    # NFS_WRITE because this exposes hostnames and IP addresses
    # READONLY is considered administrative-level permission
    @filterable(roles=['READONLY_ADMIN', 'SHARING_NFS_WRITE'])
    def get_nfs3_clients(self, filters, options):
        """
        Read contents of rmtab. This information may not
        be accurate due to stale entries. This is ultimately
        a limitation of the NFSv3 protocol.
        """
        rmtab = self.get_rmtab()
        return filter_list(rmtab, filters, options)

    @private
    def get_nfs4_client_info(self, id_):
        """
        See the following link:
            NFS 4.1 spec: https://www.rfc-editor.org/rfc/rfc8881.html
        """
        info = {}
        with suppress(FileNotFoundError):
            # The data sent by the kernel isn't always 100% valid YAML 
            # The "callback address" field is missing quotation marks.
            # So, read the whole file in Python, then if we encounter that line, 
            # add quotation marks before parsing as YAML.

            with open(f"/proc/fs/nfsd/clients/{id_}/info", "r") as f:
                yaml_data = f.readlines()

            safe_content = ""

            for line in yaml_data:
                if line.startswith("callback address") and not '"' in line:
                    payload = line.split(':', 1)[1].strip()
                    safe_content += f'callback address: "{payload}"\n'
                else:
                    safe_content += line

            info = yaml.safe_load(safe_content)

        return info

    @private
    def get_nfs4_client_states(self, id_):
        """
        Detailed information regarding current open files per NFS client
        TODO: review formatting of this field
        """
        states = []
        with suppress(FileNotFoundError):
            with open(f"/proc/fs/nfsd/clients/{id_}/states", "r") as f:
                states = yaml.safe_load(f.read())

        # states file may be empty, which changes it to None type
        # return empty list in this case
        return states or []

    # NFS_WRITE because this exposes hostnames, IP addresses and other details
    # READONLY is considered administrative-level permission
    @filterable(roles=['READONLY_ADMIN', 'SHARING_NFS_WRITE'])
    @filterable_returns(Dict(
        'client',
        Str('id'),
        Dict('info', additional_attrs=True),
        Dict('state', additional_attrs=True)
    ))
    def get_nfs4_clients(self, filters, options):
        """
        Read information about NFSv4 clients from /proc/fs/nfsd/clients
        Sample output:
        [{
            "id": "4",
            "info": {
                "clientid": 6273260596088110000,
                "address": "192.168.40.247:790",
                "status": "confirmed",
                "seconds from last renew": 45,
                "name": "Linux NFSv4.2 debian12-hv",
                "minor version": 2,
                "Implementation domain": "kernel.org",
                "Implementation name": "Linux 6.1.0-12-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.1.52-1 (2023-09-07) x86_64",
                "Implementation time": [0, 0],
                "callback state": "UP",
                "callback address": "192.168.40.247:0"
            },
            "states": [
                {
                    "94850248556250062041657638912": {
                        "type": "deleg",
                        "access": "r",
                        "superblock": "00:39:5",
                        "filename": "/debian12-hv"
                    }
                },
                {
                    "94850248556250062041741524992": {
                        "type": "open",
                        "access": "rw",
                        "deny": "--",
                        "superblock": "00:39:137",
                        "filename": "/.debian12-hv.swp",
                        "owner": "open id:\u0000\u0000\u00008\u0000\u0000\u0000\u0000\u0000\u0000\u0014þÀ²3"
                    }
                }
            ]
        }]
        ---- Description of the fields (all per NFS client) ----
        'clientid': Hash generated for this client connection
        'address':  The client IP and port. e.g. 10.20.30.40:768

        'status':   The current client status:
            'confirmed' An active connection.
                        The status will convert to 'courtesy' in 90 seconds if not 'confirmed' by the client.
            'courtesy'  A stalled connection from an inactive client.
                        The status will convert to 'expirable' in 24hr.
            'expirable' Waiting to be cleaned up.

        'seconds from last renew':  The session timeout counter.  See 'status' field.
                                    Gets reset by confirmation update from the client

        'name': Supplied by the client.
                Linux clients might offer something like 'Linux NFS4.2 clnt_name'.
                FreeBSD clients might supply a UUID like name

        'minor version':    The NFS4.x minor version.  E.G. '2' for NFSv4.2

        'Implementation domain': NFSv4.1 info - e.g. 'kernel.org' or 'freebsd.org'.
        'Implementation name':   NFSv4.1 info - e.g. equivalent to 'uname -a' on the client
        'Implementation time':   NFSv4.1 info - Timestamp (time nfstime4) of client version (maybe unused?)

        'callback state':   Current callback 'service' status for this client: 'UP', 'DOWN', 'FAULT' or 'UNKNOWN'
                            Linux clients usually indicate 'UP'
                            FreeBSD clients may indicate 'DOWN' but are still functional
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

    @accepts(roles=['SHARING_NFS_READ'])
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
