import subprocess
import contextlib
import json
import pathlib

from middlewared.utils import run
from middlewared.validators import URL
from middlewared.schema import Dict, Str
from middlewared.service import (job, accepts, private, CallError,
                                 Service, ValidationErrors)
from .utils import GlusterConfig

EVENTSD_CRE_OR_DEL = 'eventsd_cre_or_del'
LOCAL_WEBHOOK_URL = GlusterConfig.LOCAL_WEBHOOK_URL.value
WEBHOOKS_FILE = GlusterConfig.WEBHOOKS_FILE.value


class GlusterEventsdService(Service):

    class Config:
        namespace = 'gluster.eventsd'
        cli_namespace = 'service.gluster.eventsd'

    @private
    def format_cmd(self, data, delete=False,):

        cmd = ['gluster-eventsapi']
        cmd.append('webhook-add' if not delete else 'webhook-del')

        # need to add the url as the next param
        cmd.append(data['url'])

        if not delete:
            # add bearer_token
            if data.get('bearer_token'):
                cmd.append('-t')
                cmd.append(data['bearer_token'])

            # add secret
            if data.get('secret'):
                cmd.append('-s')
                cmd.append(data['secret'])

        return cmd

    @private
    def run_cmd(self, cmd):

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        out, err = proc.communicate()

        # the `out` variable is formatted PrettyTable() ouput
        # which is gross and not useful so instead of trying
        # to battle that and manipulate it the way we need
        # just raise CallError on failure otherwise 'SUCCESS'
        if proc.returncode != 0:
            raise CallError(err.strip())

        return 'SUCCESS'

    @accepts(Dict(
        'webhook_create',
        Str('url', required=True, validators=[URL()]),
        Str('bearer_token', required=False),
        Str('secret', required=False),
    ))
    @job(lock=EVENTSD_CRE_OR_DEL)
    def create(self, job, data):
        """
        Add `url` webhook that will be called
        with a JSON formatted POST request that
        will include the event that was triggered
        along with the relevant data.

        `url` is a http address (i.e. http://192.168.1.50/endpoint)
        `bearer_token` is a bearer token
        `secret` secret to encode the JWT message

        NOTE: This webhook will be synchronized to all
        peers in the trusted storage pool.
        """

        verrors = ValidationErrors()
        result = None

        cw = self.middleware.call_sync('gluster.eventsd.webhooks')
        if data['url'] not in list(cw['webhooks']):
            # there doesn't seem to be an upper limit on the amount
            # of webhook endpoints that can be added to the daemon
            # so place an arbitrary limit of 5 (for now)
            if len(cw['webhooks']) >= 5:
                verrors.add(
                    f'webhook_create.{data["url"]}',
                    'Maximum number of webhooks has been met. '
                    'Delete one or more and try again.'
                )

            verrors.check()
            cmd = self.format_cmd(data)
            result = self.run_cmd(cmd)

            # sync the file across to all other peers
            job = self.middleware.call_sync('gluster.eventsd.sync')
            job.wait_sync()

        return result

    @accepts(Dict(
        'webhook_delete',
        Str('url', required=True, validators=[URL()]),
    ))
    @job(lock=EVENTSD_CRE_OR_DEL)
    def delete(self, job, data):
        """
        Delete `url` webhook

        `url` is a http address (i.e. http://192.168.1.50/endpoint)
        """

        result = None

        # get the current webhooks
        cw = self.middleware.call_sync('gluster.eventsd.webhooks')
        if data['url'] in list(cw['webhooks']):
            cmd = self.format_cmd(data, delete=True)
            result = self.run_cmd(cmd)

            # sync the file across to all other peers
            job = self.middleware.call_sync('gluster.eventsd.sync')
            job.wait_sync()

        return result

    @accepts()
    def webhooks(self):
        """
        List the current webhooks (if any)
        """

        result = {'webhooks': {}}
        exceptions = (FileNotFoundError, json.decoder.JSONDecodeError)
        with contextlib.suppress(exceptions):
            with open(WEBHOOKS_FILE, 'r') as f:
                result['webhooks'] = json.load(f)

        return result

    @accepts()
    @job(lock='EVENTSD_SYNC')
    async def sync(self, job):
        """
        Sync the webhooks config file to all peers in the
        trusted storage pool
        """

        cp = await run(
            ['gluster-eventsapi', 'sync', '--json'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        if cp.returncode == 0:
            return json.loads(cp.stdout.strip())['output']
        else:
            raise CallError(cp.stderr.strip())

    @private
    @job(lock='eventsd_init')
    def init(self, job):
        """
        Initializes the webhook directory and config file
        if it doesn't exist.
        """

        webhook_file = pathlib.Path(WEBHOOKS_FILE)
        glusterd_dir = webhook_file.parent.parent

        # check if the glusterd dataset exists
        if glusterd_dir.exists() and glusterd_dir.is_mount():
            try:
                # make sure glusterd_dir/events subdir exists
                webhook_file.parent.mkdir(exist_ok=True)
                # create the webhooks file if it doesnt exist
                webhook_file.touch(exist_ok=True)
            except Exception as e:
                raise CallError(
                    f'Failed creating {webhook_file} with error: {e}'
                )
        else:
            raise CallError(
                f'{glusterd_dir} does not exist or is not mounted'
            )

        # at one point we tried to have glustereventsd send
        # event messages locally to us but that proved to be
        # fraught with errors because of upstream issues.
        # It's pretty clear that the glustereventsd code
        # isn't tested (or used) often because the JWT
        # implementation is very much broken so now we remove
        # localhost api endpoint (it if it's there)
        data = {'url': LOCAL_WEBHOOK_URL}
        self.middleware.call_sync('gluster.eventsd.delete', data)
