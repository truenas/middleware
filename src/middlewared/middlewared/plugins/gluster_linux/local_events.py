import aiohttp
import contextlib
import jwt
import enum

from middlewared.schema import Dict, Str, Bool
from middlewared.service import (accepts, Service,
                                 private, ValidationErrors)
from .utils import GlusterConfig


SECRETS_FILE = GlusterConfig.SECRETS_FILE.value
LOCAL_WEBHOOK_URL = GlusterConfig.LOCAL_WEBHOOK_URL.value


class AllowedEvents(enum.Enum):
    EVENTS = (
        'VOLUME_START',
        'VOLUME_STOP',
    )


class GlusterLocalEventsService(Service):

    JWT_SECRET = None

    class Config:
        namespace = 'gluster.localevents'
        cli_namespace = 'service.gluster.localevents'

    @private
    async def validate(self, data):
        verrors = ValidationErrors()
        allowed = AllowedEvents.EVENTS.value

        if data['event'] not in allowed:
            verrors.add(
                f'localevent_send.{data["event"]}',
                f'event: "{data["event"]}" is not allowed',
            )

        vols = await self.middleware.call('gluster.volume.list')
        if data['name'] not in vols:
            verrors.add(
                f'localevent_send.{data["name"]}',
                'gluster volume: "{data["name"]}" does not exist',
            )

        verrors.check()

    @accepts(Dict(
        'localevent_send',
        Str('event', required=True),
        Str('name', required=True),
        Bool('forward', default=True),
    ))
    @private
    async def send(self, data):
        await self.middleware.call('gluster.localevents.validate', data)
        secret = await self.middleware.call('gluster.localevents.get_set_jwt_secret')
        token = jwt.encode({'dummy': 'data'}, secret, algorithm='HS256')
        headers = {'JWTOKEN': token.decode('utf-8'), 'content-type': 'application/json'}
        async with aiohttp.ClientSession() as sess:
            await sess.post(LOCAL_WEBHOOK_URL, headers=headers, json=data, timeout=5)

    @accepts()
    def get_set_jwt_secret(self):
        """
        Return the secret key used to encode/decode
        JWT messages for sending/receiving gluster
        events.

        Note: this secret is only used for messages
        that are destined for the api endpoint at
        http://*:6000/_clusterevents for each peer
        in the trusted storage pool.
        """
        if self.JWT_SECRET is None:
            with contextlib.suppress(FileNotFoundError):
                with open(SECRETS_FILE, 'r') as f:
                    secret = f.read().strip()
                    if secret:
                        self.JWT_SECRET = secret

        return self.JWT_SECRET

    @accepts(Dict(
        'add_secret',
        Str('secret', required=True),
        Bool('force', default=False),
    ))
    def add_jwt_secret(self, data):
        """
        Add a `secret` key used to encode/decode
        JWT messages for sending/receiving gluster
        events.

        `secret` String representing the key to be used
                    to encode/decode JWT messages
        `force` Boolean if set to True, will forcefully
                    wipe any existing jwt key for this
                    peer. Note, if forcefully adding a
                    new key, the other peers in the TSP
                    will also need to be sent this key.

        Note: this secret is only used for messages
        that are destined for the api endpoint at
        http://*:6000/_clusterevents for each peer
        in the trusted storage pool.
        """

        if not data['force'] and self.JWT_SECRET is not None:
            verrors = ValidationErrors()
            verrors.add(
                'localevent_add_jwt_secret.{data["secret"]}',
                'An existing secret key already exists. Use force to ignore this error'
            )
            verrors.check()

        self.JWT_SECRET = data['secret']
        with open(SECRETS_FILE, 'w+') as f:
            f.write(data['secret'])
