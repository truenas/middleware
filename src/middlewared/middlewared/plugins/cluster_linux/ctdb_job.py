from middlewared.service import Service, private, job, periodic
from middlewared.service_exception import CallError
from middlewared.plugins.cluster_linux.utils import CTDBConfig

import time
import errno
import enum
import asyncio


class CLStatus(enum.Enum):
    ACTIVE = enum.auto()
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
            if i['timeout'] and now > i['timeout']:
                status = CLStatus.EXPIRED
            else:
                status = CLStatus.ACTIVE

            entry = {
                'key': i['key'],
                'pnn': pnn,
                'status': status.name,
                'method': i['value']['method'],
                'payload': i['value'].get('data', None)
            }

            if pnn not in output:
                output[pnn] = [entry]
            else:
                output[pnn].append(entry)

        return output

    @private
    @periodic(3600)
    @job(lock="queue_lock")
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
            await self.middleware.call('clustercache.pop', entry['key'])
            if entry['status'] == CLStatus.EXPIRED.name:
                continue

            try:
                if entry['payload']:
                    await self.middleware.call(entry['method'], entry['payload'])
                else:
                    await self.middleware.call(entry['method'])
            except Exception:
                self.logger.warning("Cluster cached job for method [%s] failed.", entry['method'], exc_info=True)

        job.set_progress(100, 'Finished processing queue.')

    @private
    async def wait_for_method(self, job, method, percent):
        current_node_list = []
        prefix = f'CLJOB_{method}_'

        for i in range(10):
            nodes = []
            entries = await self.middleware.call(
                'clustercache.query',
                [('key', '^', prefix)]
            )
            if not entries:
                return

            for entry in entries:
                nodes.append(int(entry['key'][len(prefix):]))

            current_node_list = nodes.copy()
            job.set_progress(percent, f'Waiting for nodes {current_node_list} to complete {method}.')
            await asyncio.sleep(5)

        raise CallError("Timed out waiting for nodes {current_node_list} to complete {method}.", errno.ETIMEDOUT)

    @private
    @job(lock="cluster_job_send")
    async def submit(self, job, method, data=None, timeout=300):
        """
        Send changes to other nodes to be applied.
        """
        payload = {'method': method, 'payload': data}

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
