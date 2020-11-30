from middlewared.service import accepts, job, CallError, CRUDService
from .utils import JOB_LOCK

import subprocess
import json


class CtdbGeneralService(CRUDService):

    class Config:
        namespace = 'ctdb.general'

    def __ctdb_wrapper(self, command):

        command = command.insert(0, 'ctdb')
        command = command.insert(1, '-j')

        result = {}
        sp = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf8',
            errors='ignore',
        )

        if not sp.returncode:
            try:
                result = json.loads(sp.stdout)
            except Exception as e:
                raise CallError(
                    'Failed parsing ctdb information with error: %s', e
                )
        else:
            raise CallError(
                'Failed running ctdb command with error %s',
                result.stderr.decode()
            )

        return result

    @accepts()
    @job(lock=JOB_LOCK)
    async def listnodes(self, job):

        """
        List the nodes in the ctdb cluster.
        """

        command = ['listnodes']
        return self.__ctdb_wrapper(command)

    @accepts()
    @job(lock=JOB_LOCK)
    def status(self, job):

        """
        Query for the status of the ctdb cluster.
        """

        command = ['status']
        return self.__ctdb_wrapper(command)
