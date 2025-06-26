import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (ISCSIPortalCreateArgs, ISCSIPortalCreateResult, ISCSIPortalDeleteArgs,
                                     ISCSIPortalDeleteResult, IscsiPortalEntry, ISCSIPortalListenIpChoicesArgs,
                                     ISCSIPortalListenIpChoicesResult, ISCSIPortalUpdateArgs, ISCSIPortalUpdateResult)
from middlewared.service import CRUDService, private, ValidationErrors


def portal_summary(data):
    """Select a human-readable string representing this portal"""
    if title := data.get('comment'):
        return title
    ips = []
    for pair in data.get('listen', []):
        if ip := pair.get('ip'):
            ips.append(ip)
    return ','.join(ips)


class ISCSIPortalModel(sa.Model):
    __tablename__ = 'services_iscsitargetportal'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_portal_tag = sa.Column(sa.Integer(), default=1)
    iscsi_target_portal_comment = sa.Column(sa.String(120))


class ISCSIPortalIPModel(sa.Model):
    __tablename__ = 'services_iscsitargetportalip'
    __table_args__ = (
        sa.Index('services_iscsitargetportalip_iscsi_target_portalip_ip', 'iscsi_target_portalip_ip', unique=True),
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
        role_prefix = 'SHARING_ISCSI_PORTAL'
        entry = IscsiPortalEntry

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
        return data

    @api_method(ISCSIPortalListenIpChoicesArgs, ISCSIPortalListenIpChoicesResult)
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
                choices[i['alias_vip']] = f'{i["alias_address"]}/{i["alias_address_b"]}'
        else:
            if await self.middleware.call('failover.licensed'):
                # If ALUA is disabled, HA system should only offer Virtual IPs
                for i in await self.middleware.call('interface.query'):
                    for alias in i.get('failover_virtual_aliases') or []:
                        choices[alias['address']] = alias['address']
            else:
                # Non-HA system should offer all addresses
                for i in await self.middleware.call('interface.query'):
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

    @api_method(
        ISCSIPortalCreateArgs,
        ISCSIPortalCreateResult,
        audit='Create iSCSI portal',
        audit_extended=lambda data: portal_summary(data)
    )
    async def do_create(self, data):
        """
        Create a new iSCSI Portal.
        """
        verrors = ValidationErrors()
        await self.__validate(verrors, data, 'iscsiportal_create')
        verrors.check()

        # tag attribute increments sequentially
        data['tag'] = (await self.middleware.call(
            'datastore.query', self._config.datastore, [], {'count': True}
        )) + 1

        listen = data.pop('listen')

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
        Update database with new listen IPs.
        It will delete no longer existing addresses and add new ones.
        """
        # We only want to compare 'ip', weed out any 'port' present
        new_listen_set = set([(('ip', i.get('ip')),) for i in new])
        old_listen_set = set([(('ip', i.get('ip')),) for i in old]) if old else set()
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

    @api_method(
        ISCSIPortalUpdateArgs,
        ISCSIPortalUpdateResult,
        audit='Update iSCSI portal',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, pk, data):
        """
        Update iSCSI Portal `id`.
        """

        old = await self.get_instance(pk)
        audit_callback(portal_summary(old))

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'iscsiportal_update', old)
        verrors.check()

        listen = new.pop('listen')

        await self.__save_listen(pk, listen, old['listen'])

        await self.middleware.call(
            'datastore.update', self._config.datastore, pk, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(pk)

    @api_method(
        ISCSIPortalDeleteArgs,
        ISCSIPortalDeleteResult,
        audit='Delete iSCSI portal',
        audit_callback=True,
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete iSCSI Portal `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(portal_summary(old))
        await self.middleware.call(
            'datastore.delete', 'services.iscsitargetgroups', [['iscsi_target_portalgroup', '=', id_]]
        )
        await self.middleware.call(
            'datastore.delete', 'services.iscsitargetportalip', [['iscsi_target_portalip_portal', '=', id_]]
        )
        result = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        for i, portal in enumerate(await self.middleware.call('iscsi.portal.query', [], {'order_by': ['tag']})):
            await self.middleware.call(
                'datastore.update', self._config.datastore, portal['id'], {'tag': i + 1},
                {'prefix': self._config.datastore_prefix}
            )

        await self._service_change('iscsitarget', 'reload')

        return result
