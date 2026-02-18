from __future__ import annotations

import stat
from typing import Any

import middlewared.sqlalchemy as sa
from middlewared.api.current import InitShutdownScriptCreate, InitShutdownScriptEntry, InitShutdownScriptUpdate
from middlewared.service import CallError, CRUDServicePart, ValidationErrors


class InitShutdownScriptModel(sa.Model):
    __tablename__ = 'tasks_initshutdown'

    id = sa.Column(sa.Integer(), primary_key=True)
    ini_type = sa.Column(sa.String(15), default='command')
    ini_command = sa.Column(sa.String(300))
    ini_script = sa.Column(sa.String(255), nullable=True)
    ini_when = sa.Column(sa.String(15))
    ini_enabled = sa.Column(sa.Boolean(), default=True)
    ini_timeout = sa.Column(sa.Integer(), default=10)
    ini_comment = sa.Column(sa.String(255))


class InitShutdownScriptServicePart(CRUDServicePart[InitShutdownScriptEntry]):
    _datastore = 'tasks.initshutdown'
    _datastore_prefix = 'ini_'
    _entry = InitShutdownScriptEntry

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        data['type'] = data['type'].upper()
        data['when'] = data['when'].upper()
        return data

    async def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data['type'] = data['type'].lower()
        data['when'] = data['when'].lower()
        return data

    async def do_create(self, data: InitShutdownScriptCreate) -> InitShutdownScriptEntry:
        await self.validate(data, 'init_shutdown_script_create')
        return await self._create(data.model_dump())

    async def do_update(self, id_: int, data: InitShutdownScriptUpdate) -> InitShutdownScriptEntry:
        old = await self.get_instance(id_)
        new = old.updated(data)
        await self.validate(new, 'init_shutdown_script_update')
        return await self._update(id_, new.model_dump())

    async def do_delete(self, id_: int) -> None:
        await self._delete(id_)

    async def validate(self, data: InitShutdownScriptCreate, schema_name: str) -> None:
        verrors = ValidationErrors()
        if data.type == 'COMMAND' and not data.command:
            verrors.add(f'{schema_name}.command', 'This field is required')
        elif data.type == 'SCRIPT':
            if not data.script:
                verrors.add(f'{schema_name}.script', 'This field is required')
            else:
                try:
                    obj = await self.middleware.call('filesystem.stat', data.script)
                except CallError as e:
                    verrors.add(f'{schema_name}.script', e.errmsg, e.errno)
                except Exception as e:
                    verrors.add(f'{schema_name}.script', str(e))
                else:
                    if obj['type'] != 'FILE':
                        verrors.add(f'{schema_name}.script', 'Script must be a regular file not {obj["type"]!r}')
                    elif not bool(obj['mode'] & stat.S_IXUSR):
                        verrors.add(f'{schema_name}.script', 'Script must have execute bit set for the user')

        verrors.check()
