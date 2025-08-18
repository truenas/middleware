import uuid
from pydantic import field_validator

import middlewared.sqlalchemy as sa

from middlewared.service import ConfigService, ValidationErrors
from middlewared.api import api_method
from middlewared.api.current import NVMeHostEntry
from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, single_argument_args


NQN_UUID_PREFIX = 'nqn.2014-08.org.nvmexpress:uuid:'


@single_argument_args('nvme_host_update')
class NVMeHostUpdateArgs(NVMeHostEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()

    @field_validator('hostid_a', 'hostid_b')
    def validate_uuid(cls, value):
        if value is not None:
            try:
                uuid.UUID(value, version=4)
            except ValueError:
                raise ValueError('UUID is not valid version 4')
        return value

    @field_validator('hostnqn_a', 'hostnqn_b')
    def validate_nqn(cls, value):
        if value is not None:
            if not value.startswith(NQN_UUID_PREFIX):
                raise ValueError(f'NQN must start with "{NQN_UUID_PREFIX}"')
            try:
                uuid.UUID(value[len(NQN_UUID_PREFIX):], version=4)
            except ValueError:
                raise ValueError('UUID portion of NQN is not valid version 4')
        return value


class NVMeHostUpdateResult(BaseModel):
    result: NVMeHostEntry


class NVMeHostModel(sa.Model):
    __tablename__ = 'storage_nvme_host'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvme_host_hostid_a = sa.Column(sa.String(32))
    nvme_host_hostnqn_a = sa.Column(sa.String())
    nvme_host_hostid_b = sa.Column(sa.String(32))
    nvme_host_hostnqn_b = sa.Column(sa.String())


class NVMeHost(ConfigService):
    class Config:
        private = True
        namespace = 'nvme.host'
        datastore = 'storage.nvme_host'
        datastore_prefix = 'nvme_host_'
        private = True
        service = 'nvme'
        entry = NVMeHostEntry

    @api_method(NVMeHostUpdateArgs, NVMeHostUpdateResult, private=True)
    async def do_update(self, data):
        old_config = await self.config()
        new = old_config.copy()
        new.update(data)

        verrors = ValidationErrors()
        self.__validate(verrors, new, 'nvme_host_update')
        verrors.check()

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            new['id'],
            new,
            {'prefix': self._config.datastore_prefix},
        )

        await self.middleware.call('etc.generate', 'nvme')
        if await self.middleware.call('failover.status') == 'MASTER':
            if await self.middleware.call('failover.remote_connected'):
                await self.middleware.call('failover.call_remote', 'etc.generate', ['nvme'])

        return await self.config()

    async def hostid(self):
        node = await self.middleware.call('failover.node')
        cfg = await self.config()
        match node:
            case 'A' | 'MANUAL':
                return cfg['hostid_a']
            case 'B':
                return cfg['hostid_b']

    async def hostnqn(self):
        node = await self.middleware.call('failover.node')
        cfg = await self.config()
        match node:
            case 'A' | 'MANUAL':
                return cfg['hostnqn_a']
            case 'B':
                return cfg['hostnqn_b']

    def __validate(self, verrors, data, schema_name, old=None):
        if data['hostid_a'] == data['hostid_b']:
            verrors.add(f'{schema_name}.hostid_b', 'Cannot use same hostid for both nodes')
        if data['hostnqn_a'] == data['hostnqn_b']:
            verrors.add(f'{schema_name}.hostnqn_b', 'Cannot use same hostnqn for both nodes')

    async def setup(self):
        payload = {}
        cfg = await self.middleware.call('nvme.host.config')
        for hostid_key in ['hostid_a', 'hostid_b']:
            if not cfg[hostid_key]:
                payload = payload | {hostid_key: str(uuid.uuid4())}
        for hostnqn_key in ['hostnqn_a', 'hostnqn_b']:
            if not cfg[hostnqn_key]:
                payload = payload | {hostnqn_key: f"{NQN_UUID_PREFIX}{uuid.uuid4()}"}
        if payload:
            await self.middleware.call('nvme.host.update', payload)
