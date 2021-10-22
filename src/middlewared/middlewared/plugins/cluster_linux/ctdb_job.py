from middlewared.service import Service, private, job, periodic
from middlewared.service_exception import CallError
from middlewared.plugins.cluster_linux.utils import CTDBConfig

import time
import errno
import enum
import asyncio


class CLStatus(enum.Enum):
    ACTIVE = enum.auto()
    RUNNING = enum.auto()
    EXPIRED = enum.auto()


class ClusterJob(Service):
    class Config:
        private = True

    async def list(self):
        """
        Return queue indexed by pnn
        """
        cl_jobs = await self.middleware.call(
            'clustercache.query',
            [('key', '^', 'CLJOB_')],
        )
        output = {}
        now = time.clock_gettime(time.CLOCK_REALTIME)

        for i in cl_jobs:
            pnn = int(i['key'].rsplit('_', 1)[1])
            is_expired = False

            if i['timeout'] and now > i['timeout']:
                is_expired = True

            entry = {
                'key': i['key'],
                'pnn': pnn,
                'status': CLStatus.EXPIRED.name if is_expired else i['value']['status'],
                'method': i['value']['method'],
                'job': i['value']['is_job'],
                'timeout': i['timeout'],
                'payload': i['value'].get('payload', None)
            }

            if pnn not in output:
                output[pnn] = [entry]
            else:
                output[pnn].append(entry)

        return output

    @private
    @periodic(3600)
    @job(lock="queue_lock", transient=True)
    async def process_queue(self, job):
        gl_enabled = (await self.middleware.call('service.query', [('service', '=', 'glusterd')], {'get': True}))['enable']
        if not gl_enabled:
            return

        node = (await self.middleware.call('ctdb.general.status', {'all_nodes': False}))[0]
        if node['flags_str'] != 'OK':
            CallError(f'Cannot reload directory service. Node health: {node["flags_str"]}')

        job_list = await self.list()
        for idx, entry in enumerate(job_list.get(node["pnn"], [])):
            p = (100 / len(job_list) * idx)
            job.set_progress(p, f'Processing queued job for [{entry["method"]}].')
            if entry['status'] == CLStatus.EXPIRED.name:
                continue

            await self.update_status(entry['key'], CLStatus.RUNNING.name, entry['timeout'])
            try:
                if entry['payload']:
                    rv = await self.middleware.call(entry['method'], entry['payload'])
                else:
                    rv = await self.middleware.call(entry['method'])
            except Exception:
                self.logger.warning("Cluster cached job for method [%s] failed.", entry['method'], exc_info=True)

            if entry['job']:
                rv = await rv.wait()

            await self.middleware.call('clustercache.pop', entry['key'])

        job.set_progress(100, 'Finished processing queue.')

    @private
    async def wait_for_method(self, job, method, percent):
        current_node_list = []
        prefix = f'CLJOB_{method}_'

        for i in range(10):
            now = time.clock_gettime(time.CLOCK_REALTIME)
            nodes = []
            entries = await self.middleware.call(
                'clustercache.query',
                [('key', '^', prefix)]
            )
            active_entries = [x for x in entries if x['timeout'] > now or x['value']['status'] == 'RUNNING']

            if not active_entries:
                return

            for entry in entries:
                nodes.append(int(entry['key'][len(prefix):]))

            current_node_list = nodes.copy()
            job.set_progress(percent, f'Waiting for nodes {current_node_list} to complete {method}.')
            await asyncio.sleep(5)

        raise CallError(f"Timed out waiting for nodes {current_node_list} to complete {method}.", errno.ETIMEDOUT)

    @private
    async def update_status(self, key, status, timeout_abs):
        now = time.clock_gettime(time.CLOCK_REALTIME)
        entry = await self.middleware.call('clustercache.get', key)
        entry['status'] = status
        new_timeout = timeout_abs - now

        await self.middleware.call('clustercache.put', key, entry, int(new_timeout), {'flag': 'REPLACE'})

    @private
    @job(lock="cluster_job_send")
    async def submit(self, job, method, data=None, timeout=300, is_job=False):
        """
        Send changes to other nodes to be applied.
        """
        payload = {
            'method': method,
            'payload': data,
            'is_job': is_job,
            'status': CLStatus.ACTIVE.name
        }

        await self.wait_for_method(job, method, 10)
        nodes = await self.middleware.call('ctdb.general.status')

        job.set_progress(50, f'Setting job status indicator for nodes {node["pnn"] for node in nodes}')
        for node in nodes:
            if node['this_node'] or node['pnn'] == -1:
                continue
            key = f'CLJOB_{method}_{node["pnn"]}'
            await self.middleware.call('clustercache.put', key, payload, timeout)

        data = {
            "event": "CLJOBS_PROCESS",
            "name": CTDBConfig.CTDB_VOL_NAME.value,
            "forward": True
        }
        await self.middleware.call('gluster.localevents.send', data)
        await self.wait_for_method(job, method, 90)
        job.set_progress(100, 'Finished submitting cluster job')
