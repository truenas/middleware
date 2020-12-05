import subprocess
import contextlib
import json

from middlewared.validators import URL
from middlewared.schema import Dict, Str
from middlewared.service import (job, accepts, CallError,
                                 CRUDService, ValidationErrors)
from .utils import GlusterConfig


EVENTSD_LOCK = GlusterConfig.EVENTSD_LOCK.value
LOCAL_WEBHOOK_URL = GlusterConfig.LOCAL_EVENTSD_WEBHOOK_URL.value
WEBHOOKS_FILE = GlusterConfig.WEBHOOKS_FILE.value


class GlusterEventsdService(CRUDService):

    class Config:
        namespace = 'gluster.eventsd'

    def format_cmd(self, data, delete=False,):

        cmd = [
            'gluster-eventsapi', 'webhook-add' if not delete else 'webhook-del'
        ]

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
    @job(lock=EVENTSD_LOCK)
    def do_create(self, job, data):

        """
        Add `url` webhook that will be called
        with a POST request that will include
        the event that was triggered along with the
        relevant data.

        `url` is a http address (i.e. http://192.168.1.50/endpoint)
        `bearer_token` is a bearer token
        `secret` secret to add JWT bearer token
        """

        verrors = ValidationErrors()

        add_it = result = None

        # get the current webhooks
        cw = self.middleware.call_sync('gluster.eventsd.webhooks')
        if data['url'] not in list(cw['webhooks']):
            add_it = True
            # there doesn't seem to be an upper limit on the amount
            # of webhook endpoints that can be added to the daemon
            # so place an arbitrary limit of 5
            # (excluding the local middlewared webhook)
            if len(cw['webhooks']) >= 5 and data['url'] != LOCAL_WEBHOOK_URL:
                verrors.add(
                    f'webhook_create.{data["url"]}',
                    'Maximum number of webhooks has been met. '
                    'Delete one or more and try again.'
                )

        verrors.check()

        if add_it:
            cmd = self.format_cmd(data)
            result = self._run_cmd(cmd)

        return result

    @accepts(Dict(
        'webhook_delete',
        Str('url', required=True, validators=[URL()]),
    ))
    @job(lock=EVENTSD_LOCK)
    def do_delete(self, job, data):

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

        return result

    @accepts()
    def webhooks(self):

        """
        List the current webhooks (if any)
        """

        result = {'webhooks': {}}
        with contextlib.suppress(FileNotFoundError):
            with open(WEBHOOKS_FILE, 'r') as f:
                result['webhooks'] = json.load(f)

        return result

    @accepts()
    @job(lock=EVENTSD_LOCK)
    def sync(self, job):

        """
        Sync the webhooks config file to all peers in the
        trusted storage pool
        """

        proc = subprocess.Popen(
            ['gluster-eventsapi', 'sync', '--json'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        out, err = proc.communicate()

        if proc.returncode == 0:
            return json.loads(out.strip())['output']
        else:
            raise CallError(err.strip())
