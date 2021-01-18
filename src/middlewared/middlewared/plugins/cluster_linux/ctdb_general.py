from middlewared.schema import Dict, Bool
from middlewared.service import CallError, Service, accepts, private
from middlewared.utils import run

import json


class CtdbGeneralService(Service):

    class Config:
        namespace = 'ctdb.general'

    @private
    async def wrapper(self, command):

        command.insert(0, 'ctdb')
        command.insert(1, '-j')

        result = {}
        parse_it = False

        cp = await run(command, check=False)
        if not cp.returncode:
            parse_it = True
        else:
            # TODO: ctdb -j listnodes always has
            # a returncode of 1. Once this is fixed
            # remove the ugly `parse_it` hack
            if 'listnodes' in command:
                parse_it = True

        if parse_it:
            try:
                result = json.loads(cp.stdout)
            except Exception as e:
                raise CallError(f'ctdb parsing failed with error: {e}')
        else:
            raise CallError(
                f'ctdb command failed with error {cp.stderr.decode().strip()}'
            )

        return result

    @accepts(Dict(
        'ctdb_status',
        Bool('all_nodes', default=True)
    ))
    async def status(self, data):
        """
        List the status of nodes in the ctdb cluster.

        `all_nodes`: Boolean if True, return status
            for all nodes in the cluster else return
            status of this node.
        """

        command = ['status' if data['all_nodes'] else 'nodestatus']
        result = await self.middleware.call('ctdb.general.wrapper', command)
        if result:
            result = result['nodes'] if not data['all_nodes'] else result['nodemap']['nodes']

        return result

    @accepts()
    async def listnodes(self):
        """
        Return a list of nodes in the ctdb cluster.
        """

        result = await self.middleware.call('ctdb.general.wrapper', ['listnodes'])
        return result['nodelist'] if result else result

    @accepts(Bool('all', default=True))
    async def ips(self, data):
        """
        Return a list of public ip addresses in the ctdb cluster.
        """
        return []

        # TODO "ctdb ips" sub-command doesn't return json output
        # so skip for now
        # command = ['ips', 'all'] if data['all'] else ['ips']
        # result = await self.middleware.call('ctdb.general.wrapper', command)
        # return result['iplist'] if result else result

    @accepts()
    async def healthy(self):
        """
        Returns a boolean if the ctdb cluster is healthy.
        """

        # TODO: ctdb has event scripts that can be run when the
        # health of the cluster has changed. We should use this
        # approach and use a lock on a file as a means of knowing
        # if the cluster status is changing when we try to read it.
        # something like:
        #   writer does this:
        #       health_file = LockFile('/file/on/disk')
        #       open('/file/on/disk').write('True or False')
        #   reader does this:
        #       health_file = LockFile('/file/on/disk')
        #       while not health_file.is_locked():
        #           return bool(open('/file/on/disk', 'r').read())
        # or something...
        status = await self.middleware.call('ctdb.general.status', {'all_nodes': True})
        return not any(map(lambda x: x['flags_str'] != 'OK', status)) if status else False
