import json
import os

import middlewared.sqlalchemy as sa

from middlewared.plugins.iscsi_.constants import DISCOVERY_AUTH_UPGRADE_COMPLETE_SENTINEL
from middlewared.schema import accepts, Dict, Int, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.validators import Range


def _auth_summary(data):
    authmethod = data.get('authmethod', '')
    authgroup = data.get('authgroup', '')
    return f'{authmethod} Group ID {authgroup}'


class iSCSIDiscoveryAuthModel(sa.Model):
    __tablename__ = 'services_iscsidiscoveryauth'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_discoveryauth_authmethod = sa.Column(sa.String(120), default='CHAP')
    iscsi_discoveryauth_authgroup = sa.Column(sa.Integer(), unique=True)


class iSCSIDiscoveryAuthService(CRUDService):

    class Config:
        namespace = 'iscsi.discoveryauth'
        datastore = 'services.iscsidiscoveryauth'
        datastore_prefix = 'iscsi_discoveryauth_'
        role_prefix = 'SHARING_ISCSI_AUTH'
        cli_namespace = 'sharing.iscsi.discoveryauth'

    ENTRY = Patch(
        'iscsi_discoveryauth_create',
        'iscsi_discoveryauth_entry',
        ('add', Int('id', required=True)),
    )

    @accepts(Dict(
        'iscsi_discoveryauth_create',
        Str('authmethod', enum=['CHAP', 'CHAP_MUTUAL'], default='CHAP'),
        Int('authgroup', validators=[Range(min_=0)]),
        register=True
    ), audit='Create iSCSI Discovery Authorized Access', audit_extended=lambda data: _auth_summary(data))
    async def do_create(self, data):
        """
        Create an iSCSI Discovery Authorized Access.

        `authmethod` specifies the CHAP mechanism that will be used for discovery authentication (only).
        Note that only a single Mutual CHAP user may be specified system-wide for discovery auth.

        `authgroup` specifies an authorized access group id to be used for discovery auth.
        """
        verrors = ValidationErrors()
        await self.validate(data, 'iscsi_discoveryauth_create', verrors)

        verrors.check()

        orig_peerusers = await self.middleware.call('iscsi.discoveryauth.mutual_chap_peerusers')

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('iscsi.discoveryauth.recalc_mutual_chap_alert', orig_peerusers)
        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'iscsi_discoveryauth_create',
            'iscsi_discoveryauth_update',
            ('attr', {'update': True})
        ),
        audit='Update iSCSI Discovery Authorized Access',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update iSCSI Authorized Access of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(_auth_summary(old))

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.validate(new, 'iscsi_discoveryauth_update', verrors)
        verrors.check()

        orig_peerusers = await self.middleware.call('iscsi.discoveryauth.mutual_chap_peerusers')

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('iscsi.discoveryauth.recalc_mutual_chap_alert', orig_peerusers)
        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id_)

    @accepts(Int('id'),
             audit='Delete iSCSI Discovery Authorized Access',
             audit_callback=True,)
    async def do_delete(self, audit_callback, id_):
        """
        Delete iSCSI Discovery Authorized Access of `id`.
        """
        config = await self.get_instance(id_)
        audit_callback(_auth_summary(config))

        orig_peerusers = await self.middleware.call('iscsi.discoveryauth.mutual_chap_peerusers')

        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id_
        )

        if not await self.middleware.call('iscsi.discoveryauth.query', [], {'count': True}):
            # If we have cleared all the discovery auth, then don't need any alerts
            await self.middleware.call('iscsi.discoveryauth.clear_alerts')
        elif orig_peerusers and len(orig_peerusers) > 1:
            # Have we eliminated the multiple mutual CHAP alert?
            await self.middleware.call('iscsi.discoveryauth.recalc_mutual_chap_alert', orig_peerusers)

        await self._service_change('iscsitarget', 'reload')
        return result

    @private
    async def validate(self, data, schema_name, verrors):
        """
        If this is an update then data will contain an `id`
        """
        authgroup = data['authgroup']
        authmethod = data['authmethod']
        id_ = data.get('id')

        # Check the specified authgroup
        if authgroup >= 0:
            if id_ is None:
                # Adding a new entry
                filters = [['authgroup', '=', authgroup]]
            else:
                # Updating an existing entry
                filters = [['authgroup', '=', authgroup], ['id', '!=', id_]]
            if await self.middleware.call('iscsi.discoveryauth.query', filters, {'count': True}):
                verrors.add(
                    f'{schema_name}.authgroup',
                    'The specified authgroup is already in use.'
                )
            if not await self.middleware.call('iscsi.auth.query', [['tag', '=', authgroup]], {'count': True}):
                verrors.add(
                    f'{schema_name}.authgroup',
                    'The specified authgroup does not contain any entries.'
                )

        if authmethod == 'CHAP_MUTUAL':
            # Ensure that we don't add more than one MUTUAL
            if id_ is None:
                # Adding a new entry
                filters = [['authmethod', '=', 'CHAP_MUTUAL']]
            else:
                # Updating an existing entry
                filters = [['authmethod', '=', 'CHAP_MUTUAL'], ['id', '!=', id_]]
            if await self.middleware.call('iscsi.discoveryauth.query', filters, {'count': True}):
                verrors.add(
                    f'{schema_name}.authmethod',
                    'Another Mutual CHAP discovery auth has already been specified.'
                )
            else:
                # Ensure that this auth does not have more than one peeruser
                filters = [['tag', '=', authgroup], ['peeruser', '!=', '']]
                if await self.middleware.call('iscsi.auth.query', filters, {'count': True}) > 1:
                    verrors.add(
                        f'{schema_name}.authgroup',
                        'The specified authgroup has multiple peerusers.'
                    )
                # Note: we may have upgraded and found ourselves in the above situation,
                # so we will also raise an alert if that is the case ... in addition to
                # preventing it here.

    @private
    async def mutual_chap_peers(self):
        """
        Return a list of (peeruser, peersecret) tuples that are in use for Mutual CHAP discovery auth.
        """
        filters = [['authmethod', '=', 'CHAP_MUTUAL']]
        options = {'select': ['authgroup']}
        groups = await self.middleware.call('iscsi.discoveryauth.query', filters, options)
        group_ids = [item['authgroup'] for item in groups]

        filters = [['peeruser', '!=', ""], ['tag', 'in', group_ids]]
        options = {'select': ['peeruser', 'peersecret']}
        peers = await self.middleware.call('iscsi.auth.query', filters, options)
        return [(peer['peeruser'], peer['peersecret']) for peer in peers]

    @private
    async def mutual_chap_peerusers(self):
        """
        Return a list of peerusers that are in use for Mutual CHAP discovery auth.
        """
        return [peer[0] for peer in await self.middleware.call('iscsi.discoveryauth.mutual_chap_peers')]

    @private
    async def recalc_mutual_chap_alert(self, orig_peerusers):
        alert_name = 'ISCSIDiscoveryAuthMultipleMutualCHAP'
        peerusers = await self.middleware.call('iscsi.discoveryauth.mutual_chap_peerusers')
        if len(orig_peerusers) > 1:
            # Alert was in place, do we need to update or remove it?
            if len(peerusers) <= 1:
                # Clear the existing alert
                await self.middleware.call("alert.oneshot_delete", alert_name, {'peeruser': orig_peerusers[0]})
            elif peerusers[0] != orig_peerusers[0]:
                # Remove old event and replace with new one.
                await self.middleware.call("alert.oneshot_delete", alert_name, {'peeruser': orig_peerusers[0]})
                await self.middleware.call("alert.oneshot_create", alert_name, {'peeruser': peerusers[0]})
        elif len(peerusers) > 1:
            # Alert was not in place, add one.
            await self.middleware.call("alert.oneshot_create", alert_name, {'peeruser': peerusers[0]})

    @private
    def load_upgrade_alerts(self):
        """
        Load any events that may have been generated during an alembic migration.
        """
        try:
            with open(DISCOVERY_AUTH_UPGRADE_COMPLETE_SENTINEL, 'r') as f:
                alerts = json.load(f)
                for alert in alerts:
                    self.middleware.call_sync("alert.oneshot_create", alert, alerts[alert])
                os.remove(DISCOVERY_AUTH_UPGRADE_COMPLETE_SENTINEL)
        except FileNotFoundError:
            pass

    @private
    async def clear_alerts(self):
        alerts = [alert for alert in await self.middleware.call('alert.list') if alert['klass'].startswith('ISCSIDiscoveryAuth')]
        for alert in alerts:
            await self.middleware.call("alert.oneshot_delete", alert['klass'], alert['args'])


async def __event_system_ready(middleware, event_type, args):
    await middleware.call('iscsi.discoveryauth.load_upgrade_alerts')


async def setup(middleware):
    if await middleware.call('system.ready'):
        await middleware.call('iscsi.discoveryauth.load_upgrade_alerts')
    else:
        middleware.event_subscribe('system.ready', __event_system_ready)
