import pam

from typing import Literal, TYPE_CHECKING

from datetime import datetime
from middlewared.api import api_method
from middlewared.api.current import (
    ApiKeyEntry, ApiKeyCreateArgs, ApiKeyCreateResult, ApiKeyUpdateArgs, ApiKeyUpdateResult,
    ApiKeyDeleteArgs, ApiKeyDeleteResult,
)
from middlewared.service import CRUDService, private, ValidationError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list
from middlewared.utils.auth import LEGACY_API_KEY_USERNAME
from middlewared.utils.crypto import generate_pbkdf2_512, generate_string
from middlewared.utils.sid import sid_is_valid
from middlewared.utils.time_utils import utc_now
if TYPE_CHECKING:
    from middlewared.main import Middleware


class APIKeyModel(sa.Model):
    __tablename__ = "account_api_key"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(200))
    user_identifier = sa.Column(sa.String(200))
    key = sa.Column(sa.Text())
    created_at = sa.Column(sa.DateTime())
    expiry = sa.Column(sa.Integer())


class ApiKeyService(CRUDService):

    class Config:
        namespace = "api_key"
        datastore = "account.api_key"
        datastore_extend = "api_key.item_extend"
        datastore_extend_context = "api_key.item_extend_ctx"
        cli_namespace = "auth.api_key"
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
            'root_name': root_name
        }

    @private
    async def item_extend(self, item, ctx):
        user_identifier = item.pop("user_identifier")
        expiry = item.pop("expiry")
        item.update({
            'username': None,
            'local': True,
            'expires_at': None,
            'revoked': False
        })
        if user_identifier.isdigit():
            # If we can't resolve the ID then the account was probably deleted
            # and we didn't quite get to clean up yet.
            item['username'] = ctx['by_id'].get(int(user_identifier))
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

        match expiry:
            case -1:
                # key has been forcibly revoked
                item['revoked'] = True
            case 0:
                # zero value indicates never expires
                pass
            case _:
                item['expires_at'] = datetime.fromtimestamp(expiry)

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

        out.pop('username', None)
        out.pop('revoked', None)
        out.pop('local', None)
        return out

    @api_method(ApiKeyCreateArgs, ApiKeyCreateResult, audit='Create API key', audit_extended=lambda data: data['name'])
    def do_create(self, data: dict) -> dict:
        """
        Creates API Key.

        `name` is a user-readable name for key.
        """
        self._validate("api_key_create", data)
        user = self.middleware.call_sync('user.query', [
            ['username', '=', data['username']]
        ])
        verrors = ValidationErrors()
        if not user:
            verrors.add('api_key_create', 'User does not exist.')

        if user and not user[0]['roles']:
            verrors.add('api_key_create', 'User lacks privilege role membership.')

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
        data["key"] = generate_pbkdf2_512(key)
        data["created_at"] = utc_now()
        data["id"] = self.middleware.call_sync(
            "datastore.insert",
            self._config.datastore,
            self.compress(data) | {'user_identifier': user_identifier}
        )

        data.update({
            'username': user[0]['username'],
            'local': False,
            'revoked': False,
        })

        self.middleware.call_sync('etc.generate', 'pam_middleware')
        return dict(data, key=f"{data['id']}-{key}")

    @api_method(ApiKeyUpdateArgs, ApiKeyUpdateResult, audit='Update API key', audit_callback=True)
    def do_update(self, audit_callback: callable, id_: int, data: dict) -> dict:
        """
        Update API Key `id`.

        Specify `reset: true` to reset this API Key.
        """
        reset = data.pop("reset", False)

        old = self.middleware.call_sync('api_key.query', [['id', '=', id_]], {'get': True})
        audit_callback(old['name'])
        new = old.copy()

        new.update(data)
        new = self._validate("api_key_update", new, id_)

        key = None
        if reset:
            key = generate_string(string_size=64)
            new["key"] = generate_pbkdf2_512(key)

        self.middleware.call_sync(
            "datastore.update",
            self._config.datastore,
            id_,
            self.compress(new),
        )

        if not key:
            return new

        self.middleware.call_sync('etc.generate', 'pam_middleware')
        return dict(new, key=f"{new['id']}-{key}")

    @api_method(ApiKeyDeleteArgs, ApiKeyDeleteResult, audit='Delete API key', audit_callback=True)
    async def do_delete(self, audit_callback: callable, id_: int) -> Literal[True]:
        """
        Delete API Key `id`.
        """
        name = (await self.get_instance(id_))['name']
        audit_callback(name)

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_
        )

        self.middleware.call_sync('etc.generate', 'pam_middleware')
        return response

    @private
    def _validate(self, schema_name: str, data: dict, id_: int = None):
        verrors = ValidationErrors()
        if self.middleware.call_sync('datastore.query', self._config.datastore, [
            ['name', '=', data['name']], ['id', '!=', id_]
        ]):
            verrors.add(schema_name, "name must be unique")

        verrors.check()

    @private
    def update_hash(self, old_key: str):
        """We have some legacy keys that have hashes generated with
        insufficient iterations. This method refreshes the hash we're storing
        with higher iterations and different algorithm"""

        id_, key = old_key.split('-', 1)
        hash = generate_pbkdf2_512(key)

        self.middleware.call_sync(
            "datastore.update",
            self._config.datastore,
            int(id_),
            {'key': hash}
        )
        self.middleware.call_sync('etc.generate', 'pam_middleware')

    @private
    async def authenticate(self, key: str) -> dict | None:
        """ Wrapper around auth.authenticate for REST API """
        try:
            key_id, key = key.split("-", 1)
            key_id = int(key_id)
        except ValueError:
            return None

        entry = await self.get_instance(key_id)
        resp = await self.middleware.call('auth.authenticate_plain',
                                          entry['username'],
                                          key,
                                          True)

        if resp['pam_response']['code'] != pam.PAM_SUCCESS:
            return None

        return resp['user_data']
