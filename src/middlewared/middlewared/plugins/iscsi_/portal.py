import errno

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Dict, Int, IPAddr, List, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors

from .utils import AUTHMETHOD_LEGACY_MAP


class ISCSIPortalModel(sa.Model):
    __tablename__ = 'services_iscsitargetportal'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_portal_tag = sa.Column(sa.Integer(), default=1)
    iscsi_target_portal_comment = sa.Column(sa.String(120))
    iscsi_target_portal_discoveryauthmethod = sa.Column(sa.String(120), default='None')
    iscsi_target_portal_discoveryauthgroup = sa.Column(sa.Integer(), nullable=True)


class ISCSIPortalIPModel(sa.Model):
    __tablename__ = 'services_iscsitargetportalip'
    __table_args__ = (
        sa.Index('services_iscsitargetportalip_iscsi_target_portalip_ip__iscsi_target_portalip_port',
                 'iscsi_target_portalip_ip', 'iscsi_target_portalip_port',
                 unique=True),
    )

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_portalip_portal_id = sa.Column(sa.ForeignKey('services_iscsitargetportal.id'), index=True)
    iscsi_target_portalip_ip = sa.Column(sa.CHAR(15))


class ISCSIPortalService(CRUDService):

    class Config:
        datastore = 'services.iscsitargetportal'
        datastore_extend = 'iscsi.portal.config_extend'
        datastore_extend_context = 'iscsi.portal.config_extend_context'
        datastore_prefix = 'iscsi_target_portal_'
        namespace = 'iscsi.portal'
        cli_namespace = 'sharing.iscsi.portal'

    @private
    async def config_extend_context(self, rows, extra):
        return {
            'global_config': await self.middleware.call('iscsi.global.config'),
        }

    @private
    async def config_extend(self, data, context):
        data['listen'] = []
        for portalip in await self.middleware.call(
            'datastore.query',
            'services.iscsitargetportalip',
            [('portal', '=', data['id'])],
            {'prefix': 'iscsi_target_portalip_'}
        ):
            data['listen'].append({
                'ip': portalip['ip'],
                'port': context['global_config']['listen_port'],
            })
        data['discovery_authmethod'] = AUTHMETHOD_LEGACY_MAP.get(
            data.pop('discoveryauthmethod')
        )
        data['discovery_authgroup'] = data.pop('discoveryauthgroup')
        return data

    @accepts()
    async def listen_ip_choices(self):
        """
        Returns possible choices for `listen.ip` attribute of portal create and update.
        """
        choices = {'0.0.0.0': '0.0.0.0', '::': '::'}
        if (await self.middleware.call('iscsi.global.config'))['alua']:
            # If ALUA is enabled we actually want to show the user the IPs of each node
            # instead of the VIP so its clear its not going to bind to the VIP even though
            # thats the value used under the hoods.
            filters = [('int_vip', 'nin', [None, ''])]
            for i in await self.middleware.call('datastore.query', 'network.Interfaces', filters):
                choices[i['int_vip']] = f'{i["int_address"]}/{i["int_address_b"]}'

            filters = [('alias_vip', 'nin', [None, ''])]
            for i in await self.middleware.call('datastore.query', 'network.Alias', filters):
                choices[i['alias_vip']] = f'{i["alias_address"]}/{i["alias_netmask"]}'
        else:
            for i in await self.middleware.call('interface.query'):
                for alias in i.get('failover_virtual_aliases') or []:
                    choices[alias['address']] = alias['address']
                for alias in i['aliases']:
                    choices[alias['address']] = alias['address']
        return choices

    async def __validate(self, verrors, data, schema, old=None):
        if not data['listen']:
            verrors.add(f'{schema}.listen', 'At least one listen entry is required.')
        else:
            system_ips = await self.listen_ip_choices()
            new_ips = set(i['ip'] for i in data['listen']) - set(i['ip'] for i in old['listen']) if old else set()
            for i in data['listen']:
                filters = [('iscsi_target_portalip_ip', '=', i['ip'])]
                if schema == 'iscsiportal_update':
                    filters.append(('iscsi_target_portalip_portal', '!=', data['id']))
                if await self.middleware.call(
                    'datastore.query', 'services.iscsitargetportalip', filters
                ):
                    verrors.add(f'{schema}.listen', f'{i["ip"]!r} IP is already in use.')

                if (
                    (i['ip'] in new_ips or not new_ips) and
                    i['ip'] not in system_ips
                ):
                    verrors.add(f'{schema}.listen', f'IP {i["ip"]} not configured on this system.')

        if data['discovery_authgroup']:
            if not await self.middleware.call(
                'datastore.query', 'services.iscsitargetauthcredential',
                [('iscsi_target_auth_tag', '=', data['discovery_authgroup'])]
            ):
                verrors.add(
                    f'{schema}.discovery_authgroup',
                    f'Auth Group "{data["discovery_authgroup"]}" not found.',
                    errno.ENOENT,
                )
        elif data['discovery_authmethod'] in ('CHAP', 'CHAP_MUTUAL'):
            verrors.add(f'{schema}.discovery_authgroup', 'This field is required if discovery method is '
                                                         'set to CHAP or CHAP Mutual.')

    @accepts(Dict(
        'iscsiportal_create',
        Str('comment'),
        Str('discovery_authmethod', default='NONE', enum=['NONE', 'CHAP', 'CHAP_MUTUAL']),
        Int('discovery_authgroup', default=None, null=True),
        List('listen', required=True, items=[
            Dict(
                'listen',
                IPAddr('ip', required=True),
            ),
        ]),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create a new iSCSI Portal.

        `discovery_authgroup` is required for CHAP and CHAP_MUTUAL.
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'iscsiportal_create')
        if verrors:
            raise verrors

        # tag attribute increments sequentially
        data['tag'] = (await self.middleware.call(
            'datastore.query', self._config.datastore, [], {'count': True}
        )) + 1

        listen = data.pop('listen')
        data['discoveryauthgroup'] = data.pop('discovery_authgroup', None)
        data['discoveryauthmethod'] = AUTHMETHOD_LEGACY_MAP.inv.get(data.pop('discovery_authmethod'), 'None')
        pk = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )
        try:
            await self.__save_listen(pk, listen)
        except Exception as e:
            await self.middleware.call('datastore.delete', self._config.datastore, pk)
            raise e

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(pk)

    async def __save_listen(self, pk, new, old=None):
        """
        Update database with a set new listen IP tuples.
        It will delete no longer existing addresses and add new ones.
        """
        new_listen_set = set([tuple(i.items()) for i in new])
        old_listen_set = set([tuple(i.items()) for i in old]) if old else set()
        for i in new_listen_set - old_listen_set:
            i = dict(i)
            await self.middleware.call(
                'datastore.insert',
                'services.iscsitargetportalip',
                {'portal': pk, 'ip': i['ip']},
                {'prefix': 'iscsi_target_portalip_'}
            )

        for i in old_listen_set - new_listen_set:
            i = dict(i)
            portalip = await self.middleware.call(
                'datastore.query',
                'services.iscsitargetportalip',
                [('portal', '=', pk), ('ip', '=', i['ip'])],
                {'prefix': 'iscsi_target_portalip_'}
            )
            if portalip:
                await self.middleware.call(
                    'datastore.delete', 'services.iscsitargetportalip', portalip[0]['id']
                )

    @accepts(
        Int('id'),
        Patch(
            'iscsiportal_create',
            'iscsiportal_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, pk, data):
        """
        Update iSCSI Portal `id`.
        """

        old = await self.get_instance(pk)

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'iscsiportal_update', old)
        if verrors:
            raise verrors

        listen = new.pop('listen')
        new['discoveryauthgroup'] = new.pop('discovery_authgroup', None)
        new['discoveryauthmethod'] = AUTHMETHOD_LEGACY_MAP.inv.get(new.pop('discovery_authmethod'), 'None')

        await self.__save_listen(pk, listen, old['listen'])

        await self.middleware.call(
            'datastore.update', self._config.datastore, pk, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(pk)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete iSCSI Portal `id`.
        """
        await self.get_instance(id)
        await self.middleware.call(
            'datastore.delete', 'services.iscsitargetgroups', [['iscsi_target_portalgroup', '=', id]]
        )
        await self.middleware.call(
            'datastore.delete', 'services.iscsitargetportalip', [['iscsi_target_portalip_portal', '=', id]]
        )
        result = await self.middleware.call('datastore.delete', self._config.datastore, id)

        for i, portal in enumerate(await self.middleware.call('iscsi.portal.query', [], {'order_by': ['tag']})):
            await self.middleware.call(
                'datastore.update', self._config.datastore, portal['id'], {'tag': i + 1},
                {'prefix': self._config.datastore_prefix}
            )

        await self._service_change('iscsitarget', 'reload')

        return result
