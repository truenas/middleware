import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Dict, Int, Password, Patch, Str
from middlewared.service import CallError, CRUDService, private, ValidationErrors


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


class iSCSITargetAuthCredentialService(CRUDService):

    class Config:
        namespace = 'iscsi.auth'
        datastore = 'services.iscsitargetauthcredential'
        datastore_prefix = 'iscsi_target_auth_'
        cli_namespace = 'sharing.iscsi.target.auth_credential'
        role_prefix = 'SHARING_ISCSI_AUTH'

    ENTRY = Patch(
        'iscsi_auth_create',
        'iscsi_auth_entry',
        ('add', Int('id', required=True)),
    )

    @accepts(Dict(
        'iscsi_auth_create',
        Int('tag', required=True),
        Str('user', required=True),
        Password('secret', required=True),
        Str('peeruser', default=''),
        Password('peersecret', default=''),
        register=True
    ), audit='Create iSCSI Authorized Access', audit_extended=lambda data: _auth_summary(data))
    async def do_create(self, data):
        """
        Create an iSCSI Authorized Access.

        `tag` should be unique among all configured iSCSI Authorized Accesses.

        `secret` and `peersecret` should have length between 12-16 letters inclusive.

        `peeruser` and `peersecret` are provided only when configuring mutual CHAP. `peersecret` should not be
        similar to `secret`.
        """
        verrors = ValidationErrors()
        await self.validate(data, 'iscsi_auth_create', verrors)

        verrors.check()

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'iscsi_auth_create',
            'iscsi_auth_update',
            ('attr', {'update': True})
        ),
        audit='Update iSCSI Authorized Access',
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
        await self.validate(new, 'iscsi_auth_update', verrors)
        if new['tag'] != old['tag'] and not await self.query([['tag', '=', old['tag']], ['id', '!=', id_]]):
            usages = await self.is_in_use_by_portals_targets(id_)
            if usages['in_use']:
                verrors.add('iscsi_auth_update.tag', usages['usages'])

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id_)

    @accepts(Int('id'),
             audit='Delete iSCSI Authorized Access',
             audit_callback=True,)
    async def do_delete(self, audit_callback, id_):
        """
        Delete iSCSI Authorized Access of `id`.
        """
        config = await self.get_instance(id_)
        audit_callback(_auth_summary(config))

        if not await self.query([['tag', '=', config['tag']], ['id', '!=', id_]]):
            usages = await self.is_in_use_by_portals_targets(id_)
            if usages['in_use']:
                raise CallError(usages['usages'])

        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id_
        )

    @private
    async def is_in_use_by_portals_targets(self, id_):
        config = await self.get_instance(id_)
        usages = []
        portals = await self.middleware.call(
            'iscsi.portal.query', [['discovery_authgroup', '=', config['tag']]], {'select': ['id']}
        )
        if portals:
            usages.append(
                f'Authorized access of {id_} is being used by portal(s): {", ".join(str(p["id"]) for p in portals)}'
            )
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
    async def validate(self, data, schema_name, verrors):
        secret = data.get('secret')
        peer_secret = data.get('peersecret')
        peer_user = data.get('peeruser', '')

        if not peer_user and peer_secret:
            verrors.add(
                f'{schema_name}.peersecret',
                'The peer user is required if you set a peer secret.'
            )

        if len(secret) < 12 or len(secret) > 16:
            verrors.add(
                f'{schema_name}.secret',
                'Secret must be between 12 and 16 characters.'
            )

        if not peer_user:
            return

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
        elif peer_secret:
            if len(peer_secret) < 12 or len(peer_secret) > 16:
                verrors.add(
                    f'{schema_name}.peersecret',
                    'Peer Secret must be between 12 and 16 characters.'
                )
