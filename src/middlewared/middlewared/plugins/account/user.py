from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from pydantic import Secret

from middlewared.api import api_method
from middlewared.api.current import (
    QueryOptions,
    TwofactorOptions,
    UserCreate,
    UserCreateArgs,
    UserCreateResult,
    UserCreateUpdateResult,
    UserDeleteArgs,
    UserDeleteOptions,
    UserDeleteResult,
    UserEntry,
    UserGetNextUidArgs,
    UserGetNextUidResult,
    UserGetUserObj,
    UserGetUserObjArgs,
    UserGetUserObjData,
    UserGetUserObjResult,
    UserHasLocalAdministratorSetUpArgs,
    UserHasLocalAdministratorSetUpResult,
    UserRenew2faSecret,
    UserRenew2faSecretArgs,
    UserRenew2faSecretResult,
    UserSetPassword,
    UserSetPasswordArgs,
    UserSetPasswordResult,
    UserSetupLocalAdministratorArgs,
    UserSetupLocalAdministratorOptions,
    UserSetupLocalAdministratorResult,
    UserShellChoicesArgs,
    UserShellChoicesResult,
    UserTwofactorConfigEntry,
    UserUnset2faSecretArgs,
    UserUnset2faSecretResult,
    UserUpdate,
    UserUpdateArgs,
    UserUpdateResult,
)
from middlewared.common.license_reconcile import LicenseReconcileAction, LicenseReconcileDelegate
from middlewared.service import GenericCRUDService, job, private
from middlewared.utils.filesystem import attrs as fs_attrs
from middlewared.utils.types import AuditCallback

from .constants import DEFAULT_HOME_PATH
from .user_2fa import (
    UserProvisioningUriArgs,
    UserProvisioningUriResult,
    UserTwofactorConfigArgs,
    UserTwofactorConfigResult,
    provisioning_uri,
    renew_2fa_secret,
    translate_username,
    twofactor_config,
    unset_2fa_secret,
)
from .user_builtin import get_builtin_user_id
from .user_crud import UserModel, UserServicePart  # noqa: F401 (UserModel registers the table)
from .user_home import do_home_copy, update_sshpubkey
from .user_local_admin import has_local_administrator_set_up, setup_local_administrator
from .user_obj import get_user_obj
from .user_set_password import set_password
from .user_shell import shell_choices
from .user_sync_builtin import sync_builtin

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.api.current import QueryOptionsCount, QueryOptionsGet
    from middlewared.job import Job
    from middlewared.main import Middleware

__all__ = ("UserService",)


class UserService(GenericCRUDService[UserEntry]):
    """
    Manage local users
    """

    _svc_part: UserServicePart

    class Config:
        datastore = "account.bsdusers"
        datastore_prefix = "bsdusr_"
        cli_namespace = "account.user"
        role_prefix = "ACCOUNT"
        entry = UserEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = UserServicePart(self.context)

    @overload
    async def query(  # type: ignore[overload-overlap]
        self,
        filters: list[Any],
        options: QueryOptionsCount,
    ) -> int: ...

    @overload
    async def query(  # type: ignore[overload-overlap]
        self,
        filters: list[Any],
        options: QueryOptionsGet,
    ) -> UserEntry: ...

    @overload
    async def query(
        self,
        filters: list[Any] | None = None,
        options: QueryOptions | None = None,
    ) -> list[UserEntry]: ...

    async def query(
        self,
        filters: list[Any] | None = None,
        options: QueryOptions | None = None,
    ) -> list[UserEntry] | UserEntry | int:
        """
        Query users with `query-filters` and `query-options`.

        If users provided by Active Directory or LDAP are not desired, then
        "local", "=", True should be added to filters.
        """
        return await self._svc_part.query(filters or [], options or QueryOptions())

    @api_method(
        UserCreateArgs,
        UserCreateResult,
        audit="Create user",
        audit_extended=lambda data: data["username"],
        check_annotations=True,
    )
    def do_create(self, data: UserCreate) -> UserCreateUpdateResult:
        """
        Create a new user.
        """
        return self._svc_part.do_create(data)

    @api_method(
        UserUpdateArgs,
        UserUpdateResult,
        audit="Update user",
        audit_callback=True,
        pass_app=True,
        check_annotations=True,
    )
    def do_update(
        self,
        app: App,
        audit_callback: AuditCallback,
        id_: int,
        data: UserUpdate,
    ) -> UserCreateUpdateResult:
        """
        Update attributes of an existing user.
        """
        return self._svc_part.do_update(app, audit_callback, id_, data)

    @api_method(
        UserDeleteArgs,
        UserDeleteResult,
        audit="Delete user",
        audit_callback=True,
        pass_app=True,
        check_annotations=True,
    )
    def do_delete(
        self,
        app: App,
        audit_callback: AuditCallback,
        id_: int,
        options: UserDeleteOptions | None = None,
    ) -> int:
        """
        Delete user ``id``.
        """
        if options is None:
            options = UserDeleteOptions()

        return self._svc_part.do_delete(app, audit_callback, id_, options)

    @api_method(UserShellChoicesArgs, UserShellChoicesResult, check_annotations=True)
    def shell_choices(self, group_ids: list[int]) -> dict[str, str]:
        """
        Return the available shell choices to be used in :method:`user.create` and
        :method:`user.update`.
        """
        return shell_choices(self.context, group_ids)

    @api_method(UserGetUserObjArgs, UserGetUserObjResult, roles=["ACCOUNT_READ"], check_annotations=True)
    def get_user_obj(self, data: UserGetUserObj) -> UserGetUserObjData:
        """
        Returns dictionary containing information from struct passwd for the user specified by either
        the ``username`` or ``uid``. Bypasses user cache.

        .. note::

            Results will not include nested groups for Active Directory users.
        """
        return get_user_obj(self.context, data)

    @api_method(UserGetNextUidArgs, UserGetNextUidResult, roles=["ACCOUNT_READ"], check_annotations=True)
    def get_next_uid(self) -> int:
        """
        Get the next available/free uid.
        """
        return self._svc_part.get_next_uid()

    @api_method(
        UserHasLocalAdministratorSetUpArgs,
        UserHasLocalAdministratorSetUpResult,
        authentication_required=False,
        check_annotations=True,
    )
    async def has_local_administrator_set_up(self) -> bool:
        """
        Return whether a local administrator with a valid password exists.

        This is used when the system is installed without a password and must be set on
        first use/login.
        """
        return await has_local_administrator_set_up(self.context)

    @api_method(
        UserSetupLocalAdministratorArgs,
        UserSetupLocalAdministratorResult,
        audit="Set up local administrator",
        authentication_required=False,
        pass_app=True,
        check_annotations=True,
    )
    async def setup_local_administrator(
        self,
        app: App,
        username: Literal["root", "truenas_admin"],
        password: Secret[str],
        options: UserSetupLocalAdministratorOptions,
    ) -> None:
        """
        Set up local administrator (this method does not require authentication if local administrator is not already
        set up).
        """
        await setup_local_administrator(self.context, username, password.get_secret_value(), options)

    @api_method(
        UserSetPasswordArgs,
        UserSetPasswordResult,
        audit="Set account password",
        audit_extended=lambda data: data["username"],
        authorization_required=False,
        pass_app=True,
        pass_app_require=True,
        check_annotations=True,
    )
    async def set_password(self, app: App, data: UserSetPassword) -> None:
        """
        Set the password of the specified ``username`` to the ``new_password``
        specified in payload.

        A JSON-RPC ``error`` response (code ``-32602``, *Invalid params*) is returned in the
        following situations:

        - the user does not exist
        - the account is not local to the NAS (Active Directory, LDAP, etc.)
        - the account has password authentication disabled
        - the account is locked

        .. note::

            When the authenticated session has less than the ``FULL_ADMIN`` role, password changes
            will be rejected if the payload does not match the currently-authenticated user. Users
            authenticated with a one-time password are exempt and may change the password without
            submitting it a second time.
        """
        await set_password(self.context, app, data)

    @api_method(UserProvisioningUriArgs, UserProvisioningUriResult, private=True, check_annotations=True)
    async def provisioning_uri(self, username: str) -> str:
        """
        Returns the provisioning URI for the OTP for `username`. This can then be encoded in a QR code and used
        to provision an OTP app like Google Authenticator.

        WARNING: response for this endpoint includes the 2FA secret for the user
        """
        return await provisioning_uri(self.context, username)

    @api_method(UserTwofactorConfigArgs, UserTwofactorConfigResult, private=True, check_annotations=True)
    async def twofactor_config(self, username: str) -> UserTwofactorConfigEntry:
        """
        Returns two-factor authentication configuration settings for specified `username`.

        WARNING: response for this endpoint includes the 2FA secret for the user
        """
        return await twofactor_config(self.context, username)

    @api_method(
        UserUnset2faSecretArgs,
        UserUnset2faSecretResult,
        audit="Unset two-factor authentication secret:",
        audit_extended=lambda username, force=False: username,
        roles=["ACCOUNT_WRITE"],
        check_annotations=True,
    )
    async def unset_2fa_secret(self, username: str, force: bool = False) -> None:
        """
        Unset two-factor authentication secret for ``username``.
        """
        await unset_2fa_secret(self.context, username, force)

    @api_method(
        UserRenew2faSecretArgs,
        UserRenew2faSecretResult,
        audit="Renew two-factor authentication secret:",
        audit_extended=lambda username, options, force=False: username,
        authorization_required=False,
        pass_app=True,
        check_annotations=True,
    )
    async def renew_2fa_secret(
        self,
        app: App,
        username: str,
        twofactor_options: TwofactorOptions,
        force: bool = False,
    ) -> UserRenew2faSecret:
        """
        Renew ``username`` user's two-factor authentication secret.

        .. note::

            This username must match the authenticated username unless authenticated
            credentials have the ``FULL_ADMIN`` role.
        """
        return await renew_2fa_secret(self.context, app, username, twofactor_options, force)

    @private
    async def translate_username(self, username: str) -> UserEntry:
        return await translate_username(self.context, username)

    @private
    async def get_builtin_user_id(self, username: str) -> int:
        return await get_builtin_user_id(self.context, username)

    @private
    def sync_builtin(self) -> None:
        sync_builtin(self.context)

    @private
    def update_sshpubkey(self, homedir: str, user: dict[str, Any], group: str) -> None:
        update_sshpubkey(self.context, homedir, user, group)

    @private
    @job(lock=lambda args: f"copy_home_to_{args[1]}")
    def do_home_copy(
        self,
        job: Job,
        home_old: str,
        home_new: str,
        username: str,
        new_mode: str | None,
        uid: int,
    ) -> dict[str, Any] | None:
        return do_home_copy(self.context, job, home_old, home_new, username, new_mode, uid)


class UserLicenseReconcileDelegate(LicenseReconcileDelegate):
    name = "user"
    etc_groups = ("user",)
    service = "user"
    action = LicenseReconcileAction.RELOAD
    order = 20


async def setup(middleware: Middleware) -> None:
    try:
        # ensure that our default home path is always immutable. If it's not immutable then
        # pam_mkhomedir will start creating dirs within it on user login
        await middleware.run_in_thread(
            fs_attrs.set_zfs_file_attributes_dict,
            DEFAULT_HOME_PATH,
            {"immutable": True},
        )
    except Exception:
        middleware.logger.error("Failed to set immutable property on %r", DEFAULT_HOME_PATH, exc_info=True)

    await middleware.call2(
        middleware.services.truenas.license.register_reconcile_delegate,
        UserLicenseReconcileDelegate(),
    )

    if await middleware.call2(middleware.services.keyvalue.get, "run_migration", False):
        await middleware.call2(middleware.services.user.sync_builtin)
