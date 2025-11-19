import errno

from typing import Literal

from datetime import datetime, UTC
from middlewared.api import api_method
from middlewared.api.current import (
    ApiKeyEntry, ApiKeyCreateArgs, ApiKeyCreateResult, ApiKeyUpdateArgs, ApiKeyUpdateResult,
    ApiKeyDeleteArgs, ApiKeyDeleteResult, ApiKeyMyKeysArgs, ApiKeyMyKeysResult,
)
from middlewared.service import CRUDService, pass_app, private, ValidationErrors
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.utils.filter_list import filter_list
from middlewared.utils.account.authenticator import ApiKeyPamAuthenticator
from middlewared.utils.auth import LEGACY_API_KEY_USERNAME
from middlewared.utils.crypto import generate_api_key_auth_data, generate_string
from middlewared.utils.origin import ConnectionOrigin
from middlewared.utils.privilege import credential_has_full_admin
from middlewared.utils.sid import sid_is_valid
from middlewared.utils.time_utils import utc_now
from truenas_pypam import PAMCode


class APIKeyModel(sa.Model):
    __tablename__ = "account_api_key"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(200))
    user_identifier = sa.Column(sa.String(200))
    iterations = sa.Column(sa.Integer())
    salt = sa.Column(sa.EncryptedText())
    server_key = sa.Column(sa.EncryptedText())
    stored_key = sa.Column(sa.EncryptedText())
    created_at = sa.Column(sa.DateTime())
    expiry = sa.Column(sa.Integer())
    revoked_reason = sa.Column(sa.Text(), nullable=True)


class ApiKeyService(CRUDService):

    class Config:
        namespace = "api_key"
        datastore = "account.api_key"
        datastore_extend = "api_key.item_extend"
        datastore_extend_context = "api_key.item_extend_ctx"
        cli_namespace = "auth.api_key"
        role_prefix = 'API_KEY'
        entry = ApiKeyEntry

    @private
    async def item_extend_ctx(self, rows, extra):
        # user.query performs somewhat expensive datastore extend that we perhaps
        # don't care about (for example 2FA status)
        users = await self.middleware.call(
            'datastore.query', 'account.bsdusers',
            [], {'prefix': 'bsdusr_'}
        )

        by_id = {x['id']: x['username'] for x in users}

        # We want to convert legacy keys into the appropriate local
        # administrator account
        if (admin_user := filter_list(users, [['uid', '=', 950]])):
            root_name = admin_user[0]['username']
        else:
            root_name = 'root'

        return {
            'by_id': by_id,
            'by_sid': {},
            'now': utc_now(naive=False),
            'root_name': root_name
        }

    @private
    async def item_extend(self, item, ctx):
        """
        * modify `user_identifier` (change type if digit, add INVALID prefix before garbage)
        * remove `expiry`
        * add `username` - `user_identifer` is used for lookup
        * add `local`
        * add `expires_at` - derived from `expiry`
        * add `revoked` - derived from `expiry`
        """
        user_identifier = item['user_identifier']
        expiry = item.pop('expiry')

        item.update({
            'username': None,
            'local': True,
            'expires_at': None,
            'revoked': False
        })
        if user_identifier.isdigit():
            # If we can't resolve the ID then the account was probably deleted
            # and we didn't quite get to clean up yet.
            item['user_identifier'] = int(user_identifier)
            item['username'] = ctx['by_id'].get(item['user_identifier'])
        elif user_identifier == LEGACY_API_KEY_USERNAME:
            # This may be magic string designating a migrated API key
            item['username'] = ctx['root_name']
        elif sid_is_valid(user_identifier):
            if (username := ctx['by_sid'].get(user_identifier)) is None:
                resp = await self.middleware.call('idmap.convert_sids', [user_identifier])
                if entry := resp['mapped'].get(user_identifier):
                    username = entry['name']
                    # Feed SID we looked up back into our extend context
                    # Because there may be multiple keys for same SID value
                    ctx['by_sid'][user_identifier] = username

            if username:
                item['username'] = username
        else:
            # Something wildly invalid got written, but we can't
            # write a log message here (queried too frequently).
            item['username'] = None
            item['local'] = True

        if item['username'] is None:
            # prevent keys we can't resolve from being written
            item['revoked'] = True
            item['revoked_reason'] = 'User does not exist'

        match expiry:
            case -1:
                # key has been forcibly revoked
                item['revoked'] = True
            case 0 | None:
                # zero value indicates never expires
                pass
            case _:
                item['expires_at'] = datetime.fromtimestamp(expiry, UTC)

        return item

    @private
    def compress(self, data: dict) -> dict:
        out = data.copy()
        if 'expires_at' in out:
            if (expires_at := out.pop('expires_at')) is None:
                out['expiry'] = 0
            else:
                out['expiry'] = int(expires_at.timestamp())

        if out.get('revoked'):
            out['expiry'] = -1

        for key in [
            'username',
            'revoked',
            'local',
            'client_key',
        ]:
            out.pop(key, None)

        return out

    @api_method(
        ApiKeyCreateArgs,
        ApiKeyCreateResult,
        audit='Create API key',
        audit_extended=lambda data: data['name'],
        roles=['READONLY_ADMIN', 'API_KEY_WRITE'],
        pass_app=True,
    )
    def do_create(self, app, data: dict) -> dict:
        """
        Creates API Key.

        `name` is a user-readable name for key.
        """
        if self.middleware.call_sync('system.security.config')['enable_gpos_stig']:
            raise CallError(
                'Changes to API keys are not permitted in GPOS STIG mode',
                errno.EACCES
            )

        # First catch any privilege errors to avoid leaking potentially sensitive information
        self.api_key_privilege_check(app, data['username'], 'api_key.create')

        verrors = ValidationErrors()
        self._validate("api_key_create", data, verrors)
        user = self.middleware.call_sync('user.query', [
            ['username', '=', data['username']]
        ])
        if not user:
            verrors.add('api_key_create', 'User does not exist.')

        if user and not user[0]['roles']:
            verrors.add('api_key_create', 'User lacks privilege role membership.')

        verrors.check()

        if user[0]['local']:
            user_identifier = str(user[0]['id'])
        elif user[0]['sid']:
            user_identifier = user[0]['sid']
        else:
            # DS, but no SID available, fall back
            # to our synthesized DB ID (which is derived
            # from the UID of user)
            user_identifier = str(user[0]['id'])
        key = generate_string(string_size=64)
        auth_data = generate_api_key_auth_data(key)
        data.update(auth_data)

        data['created_at'] = utc_now()
        data['user_identifier'] = user_identifier
        data['id'] = self.middleware.call_sync(
            'datastore.insert',
            self._config.datastore,
            self.compress(data)
        )

        data.update({
            'username': user[0]['username'],
            'local': user[0]['local'],
            'revoked': False,
            'revoked_reason': None,
        })

        self.middleware.call_sync('etc.generate', 'pam_middleware')
        return dict(data, key=f"{data['id']}-{key}")

    @api_method(
        ApiKeyUpdateArgs,
        ApiKeyUpdateResult,
        audit='Update API key',
        audit_callback=True,
        roles=['READONLY_ADMIN', 'API_KEY_WRITE'],
        pass_app=True,
    )
    def do_update(self, app, audit_callback: callable, id_: int, data: dict) -> dict:
        """
        Update API Key `id`.

        Specify `reset: true` to reset this API Key.
        """
        if self.middleware.call_sync('system.security.config')['enable_gpos_stig']:
            raise CallError(
                'Changes to API keys are not permitted in GPOS STIG mode',
                errno.EACCES
            )

        reset = data.pop("reset", False)

        old = self.middleware.call_sync('api_key.query', [['id', '=', id_]], {'get': True})
        audit_callback(old['name'])
        new = old.copy()

        new.update(data)

        self.api_key_privilege_check(app, new['username'], 'api_key.update')

        verrors = ValidationErrors()
        self._validate("api_key_update", new, verrors, id_)
        verrors.check()
        key = None
        if reset:
            key = generate_string(string_size=64)
            auth_data = generate_api_key_auth_data(key)
            new.update(auth_data)
            new['revoked'] = False

        self.middleware.call_sync(
            'datastore.update',
            self._config.datastore,
            id_,
            self.compress(new),
        )

        if not key:
            return new

        self.middleware.call_sync('etc.generate', 'pam_middleware')
        self.middleware.call_sync('api_key.check_status')
        return dict(new, key=f"{new['id']}-{key}")

    @api_method(
        ApiKeyDeleteArgs,
        ApiKeyDeleteResult,
        audit='Delete API key',
        audit_callback=True,
        roles=['READONLY_ADMIN', 'API_KEY_WRITE'],
        pass_app=True,
    )
    async def do_delete(self, app, audit_callback: callable, id_: int) -> Literal[True]:
        """
        Delete API Key `id`.
        """
        api_key = await self.get_instance(id_)
        audit_callback(api_key['name'])

        self.api_key_privilege_check(app, api_key['username'], 'api_key.delete')

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_
        )

        await self.middleware.call('etc.generate', 'pam_middleware')
        await self.check_status()
        return response

    @private
    def _validate(self, schema_name: str, data: dict, verrors: ValidationErrors, id_: int = None):
        if self.middleware.call_sync('datastore.query', self._config.datastore, [
            ['name', '=', data['name']], ['id', '!=', id_]
        ]):
            verrors.add(schema_name, "name must be unique")

        if (expiration := data.get('expires_at')) is not None:
            if utc_now(naive=False) > expiration:
                verrors.add(schema_name, 'Expiration date is in the past')

    @private
    def api_key_privilege_check(self, app, username: str, method_name: str) -> None:
        if not app or not app.authenticated_credentials.is_user_session:
            # internal session
            return

        if credential_has_full_admin(app.authenticated_credentials):
            return

        if app.authenticated_credentials.has_role('API_KEY_WRITE'):
            return

        auth_user = app.authenticated_credentials.user['username']

        if auth_user != username:
            raise CallError(
                f'{auth_user}: authenticated user lacks privileges to create or '
                'modify API keys of other users.', errno.EACCES
            )

    @private
    @pass_app(require=True)
    async def authenticate(self, app, key: str, origin: ConnectionOrigin) -> dict | None:
        """Wrapper around `auth.authenticate` for file upload endpoint."""
        try:
            key_id = int(key.split('-', 1)[0])
        except ValueError:
            return None


        auth_ctx = app.authentication_context
        if not auth_ctx:
            raise CallError('Authentication context was not initialized')


        if auth_ctx.pam_hdl:
            raise CallError(f'{auth_ctx.pam_hdl}: Unexpected existing authenticator')

        entry = await self.get_instance(key_id)

        auth_ctx.pam_hdl = ApiKeyPamAuthenticator(username=entry['username'] or 'root', origin=origin)

        resp = await self.middleware.call('auth.authenticate_plain',
                                          entry['username'],
                                          key, app=app)

        if resp['pam_response']['code'] != PAMCode.PAM_SUCCESS:
            return None

        return (resp['user_data'], {
            'id': entry['id'],
            'name': entry['name'],
        })

    @private
    async def revoke(self, key_id, reason):
        """ Revoke the specified API key in the DB, deactivate in the pam_tdb file, and
        generate a middleware alert that it has been revoked. This is a private method
        that is called when API key passed as plain-text over insecure transport."""
        await self.middleware.call('datastore.update', self._config.datastore, key_id, {
            'expiry': -1,
            'revoked_reason': reason,
        })
        await self.middleware.call('etc.generate', 'pam_middleware')
        await self.check_status()

    @api_method(ApiKeyMyKeysArgs, ApiKeyMyKeysResult, roles=['READONLY_ADMIN', 'API_KEY_READ'],
                pass_app=True, pass_app_require=True)
    async def my_keys(self, app) -> list:
        """ Get the existing API keys for the currently-authenticated user """
        if not app.authenticated_credentials.is_user_session:
            raise CallError('Not a user session')

        username = app.authenticated_credentials.user['username']
        return await self.query([['username', '=', username]])

    @private
    async def check_status(self) -> None:
        await self.middleware.call("alert.alert_source_clear_run", "ApiKeyRevoked")
