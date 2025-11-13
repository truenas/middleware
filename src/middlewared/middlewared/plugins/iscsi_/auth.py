import middlewared.sqlalchemy as sa
from middlewared.alert.source.discovery_auth import UPGRADE_ALERTS
from middlewared.api import api_method
from middlewared.api.current import (iSCSITargetAuthCredentialCreateArgs, iSCSITargetAuthCredentialCreateResult, iSCSITargetAuthCredentialDeleteArgs,
                                     iSCSITargetAuthCredentialDeleteResult, iSCSITargetAuthCredentialEntry, iSCSITargetAuthCredentialUpdateArgs, iSCSITargetAuthCredentialUpdateResult)
from middlewared.service import CallError, CRUDService, ValidationErrors, private
from .utils import IscsiAuthType


INVALID_CHARACTERS = '#'


def _auth_summary(data):
    user = data.get('user', '')
    tag = data.get('tag', '')
    if peeruser := data.get('peeruser'):
        return f'{user}/{peeruser} ({tag})'
    return f'{user} ({tag})'


class iSCSITargetAuthCredentialModel(sa.Model):
    __tablename__ = 'services_iscsitargetauthcredential'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_target_auth_tag = sa.Column(sa.Integer(), default=1)
    iscsi_target_auth_user = sa.Column(sa.String(120))
    iscsi_target_auth_secret = sa.Column(sa.EncryptedText())
    iscsi_target_auth_peeruser = sa.Column(sa.String(120))
    iscsi_target_auth_peersecret = sa.Column(sa.EncryptedText())
    iscsi_target_auth_discovery_auth = sa.Column(sa.String(20), default=IscsiAuthType.NONE)


class iSCSITargetAuthCredentialService(CRUDService):

    class Config:
        namespace = 'iscsi.auth'
        datastore = 'services.iscsitargetauthcredential'
        datastore_prefix = 'iscsi_target_auth_'
        cli_namespace = 'sharing.iscsi.target.auth_credential'
        role_prefix = 'SHARING_ISCSI_AUTH'
        entry = iSCSITargetAuthCredentialEntry

    @api_method(iSCSITargetAuthCredentialCreateArgs, iSCSITargetAuthCredentialCreateResult, audit='Create iSCSI Authorized Access', audit_extended=lambda data: _auth_summary(data))
    async def do_create(self, data):
        """
        Create an iSCSI Authorized Access.

        `tag` should be unique among all configured iSCSI Authorized Accesses.

        `secret` and `peersecret` should have length between 12-16 letters inclusive.

        `peeruser` and `peersecret` are provided only when configuring mutual CHAP. `peersecret` should not be
        similar to `secret`.
        """
        orig_peerusers = await self.middleware.call('iscsi.auth.da_mutual_chap_peerusers')

        verrors = ValidationErrors()
        await self.validate(data, 'iscsi_auth_create', verrors, len(orig_peerusers))

        verrors.check()

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('iscsi.auth.recalc_mutual_chap_alert', orig_peerusers)
        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(data['id'])

    @api_method(iSCSITargetAuthCredentialUpdateArgs, iSCSITargetAuthCredentialUpdateResult, audit='Update iSCSI Authorized Access', audit_callback=True)
    async def do_update(self, audit_callback, id_, data):
        """
        Update iSCSI Authorized Access of `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(_auth_summary(old))

        new = old.copy()
        new.update(data)

        orig_peerusers = await self.middleware.call('iscsi.auth.da_mutual_chap_peerusers')

        verrors = ValidationErrors()
        await self.validate(new, 'iscsi_auth_update', verrors, len(orig_peerusers))
        if new['tag'] != old['tag'] and not await self.query([['tag', '=', old['tag']], ['id', '!=', id_]]):
            usages = await self.is_in_use(id_)
            if usages['in_use']:
                verrors.add('iscsi_auth_update.tag', usages['usages'])

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('iscsi.auth.recalc_mutual_chap_alert', orig_peerusers)

        # We might have cleared some junk
        await self.middleware.call('alert.alert_source_clear_run', 'ISCSIAuthSecret')

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id_)

    @api_method(iSCSITargetAuthCredentialDeleteArgs, iSCSITargetAuthCredentialDeleteResult, audit='Delete iSCSI Authorized Access', audit_callback=True)
    async def do_delete(self, audit_callback, id_):
        """
        Delete iSCSI Authorized Access of `id`.
        """
        config = await self.get_instance(id_)
        audit_callback(_auth_summary(config))

        if not await self.query([['tag', '=', config['tag']], ['id', '!=', id_]]):
            # We are attempting to delete the last auth in a particular group (aka tag)
            usages = await self.is_in_use(id_)
            if usages['in_use']:
                raise CallError(usages['usages'])

        orig_peerusers = await self.middleware.call('iscsi.auth.da_mutual_chap_peerusers')

        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id_
        )
        if orig_peerusers:
            await self.middleware.call('iscsi.auth.recalc_mutual_chap_alert', orig_peerusers)

        # We might have cleared some junk
        await self.middleware.call('alert.alert_source_clear_run', 'ISCSIAuthSecret')

        await self._service_change('iscsitarget', 'reload')

        return result

    @private
    async def is_in_use(self, id_):
        config = await self.get_instance(id_)
        usages = []
        # Check targets
        groups = await self.middleware.call(
            'datastore.query', 'services.iscsitargetgroups', [['iscsi_target_authgroup', '=', config['tag']]]
        )
        if groups:
            usages.append(
                f'Authorized access of {id_} is being used by following target(s): '
                f'{", ".join(str(g["iscsi_target"]["id"]) for g in groups)}'
            )

        return {'in_use': bool(usages), 'usages': '\n'.join(usages)}

    @private
    def _validate_secret(self, secret, fieldname, title, schema_name, verrors):
        if len(secret) < 12 or len(secret) > 16:
            verrors.add(
                f'{schema_name}.{fieldname}',
                f'{title} must be between 12 and 16 characters.'
            )
        if secret != secret.strip():
            verrors.add(
                f'{schema_name}.{fieldname}',
                f'{title} contains leading or trailing space.'
            )
        if bad_chars := [ch for ch in INVALID_CHARACTERS if ch in secret]:
            verrors.add(
                f'{schema_name}.{fieldname}',
                f'{title} contains invalid characters: {",".join(bad_chars)}'
            )

    @private
    async def validate(self, data, schema_name, verrors, discovery_auth_mutual_chap_count):
        secret = data.get('secret')
        peer_secret = data.get('peersecret')
        peer_user = data.get('peeruser', '')
        discovery_auth = data.get('discovery_auth')

        if not peer_user and peer_secret:
            verrors.add(
                f'{schema_name}.peersecret',
                'The peer user is required if you set a peer secret.'
            )

        self._validate_secret(secret, 'secret', 'Secret', schema_name, verrors)

        if peer_user:
            if not peer_secret:
                verrors.add(
                    f'{schema_name}.peersecret',
                    'The peer secret is required if you set a peer user.'
                )
            elif peer_secret == secret:
                verrors.add(
                    f'{schema_name}.peersecret',
                    'The peer secret cannot be the same as user secret.'
                )
            else:
                self._validate_secret(peer_secret, 'peersecret', 'Peer Secret', schema_name, verrors)
            if discovery_auth == IscsiAuthType.CHAP_MUTUAL and discovery_auth_mutual_chap_count:
                verrors.add(
                    f'{schema_name}.discovery_auth',
                    f'Cannot specify {IscsiAuthType.CHAP_MUTUAL} as only one such entry is permitted.'
                )
        else:
            if discovery_auth == IscsiAuthType.CHAP_MUTUAL:
                verrors.add(
                    f'{schema_name}.discovery_auth',
                    f'Cannot specify {IscsiAuthType.CHAP_MUTUAL} if peer_user has not been defined.'
                )

    @private
    async def da_mutual_chap_peerusers(self):
        """
        Return a list of peerusers that are in use for Mutual CHAP discovery auth.
        """
        filters = [['discovery_auth', '=', IscsiAuthType.CHAP_MUTUAL], ['peeruser', '!=', '']]
        options = {'select': ['peeruser']}
        return [entry['peeruser'] for entry in await self.middleware.call('iscsi.auth.query', filters, options)]

    @private
    async def recalc_mutual_chap_alert(self, orig_peerusers):
        alert_name = 'ISCSIDiscoveryAuthMultipleMutualCHAP'
        peerusers = await self.middleware.call('iscsi.auth.da_mutual_chap_peerusers')
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
    async def load_upgrade_alerts(self):
        """
        Load any events that may have been generated during an alembic migration.
        """
        for alert in UPGRADE_ALERTS:
            try:
                args = await self.middleware.call("keyvalue.get", alert)
                await self.middleware.call("alert.oneshot_create", alert, args)
                await self.middleware.call("keyvalue.delete", alert)
            except KeyError:
                pass

    @private
    async def clear_alerts(self):
        alerts = [alert for alert in await self.middleware.call('alert.list') if alert['klass'].startswith('ISCSIDiscoveryAuth')]
        for alert in alerts:
            await self.middleware.call("alert.oneshot_delete", alert['klass'], alert['args'])


async def __event_system_ready(middleware, event_type, args):
    await middleware.call('iscsi.auth.load_upgrade_alerts')


async def setup(middleware):
    if await middleware.call('system.ready'):
        await middleware.call('iscsi.auth.load_upgrade_alerts')
    else:
        middleware.event_subscribe('system.ready', __event_system_ready)
