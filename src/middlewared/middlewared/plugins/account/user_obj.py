from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal

import wbclient

from middlewared.api.current import QueryOptions, UserGetUserObj, UserGetUserObjData
from middlewared.plugins.idmap_ import idmap_sss, idmap_winbind
from middlewared.service import ValidationErrors
from middlewared.service_exception import MatchNotFound
from middlewared.utils.nss import pwd
from middlewared.utils.nss.nss_common import NssModule
from middlewared.utils.nss.pwd import PasswdDict

from .constants import SYNTHETIC_CONTAINER_ROOT

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

__all__ = ("get_user_obj",)

NssSource = Literal["LOCAL", "ACTIVEDIRECTORY", "LDAP"]

NSS_SOURCES: dict[str, NssSource] = {
    NssModule.FILES.name: "LOCAL",
    NssModule.WINBIND.name: "ACTIVEDIRECTORY",
    NssModule.SSS.name: "LDAP",
}


def get_user_obj(context: ServiceContext, data: UserGetUserObj) -> UserGetUserObjData:
    verrors = ValidationErrors()
    if not data.username and data.uid is None:
        verrors.add("get_user_obj.username", 'Either "username" or "uid" must be specified.')

    if data.username and data.uid is not None:
        verrors.add("get_user_obj.username", '"username" and "uid" may not be simultaneously specified')
    verrors.check()

    # Return the container root if requested
    if data.username == SYNTHETIC_CONTAINER_ROOT["pw_name"] or data.uid == SYNTHETIC_CONTAINER_ROOT["pw_uid"]:
        return UserGetUserObjData(**SYNTHETIC_CONTAINER_ROOT)

    # NOTE: per request from UI team we are overriding default library
    # KeyError message with a clearer one
    #
    # Many callers to user.get_user_obj may be catching KeyError and so
    # changing exception type is something that should be approached
    # carefully.
    if data.username:
        try:
            user_obj: PasswdDict = pwd.getpwnam(data.username, as_dict=True)
        except KeyError:
            raise KeyError(f"{data.username}: user with this name does not exist") from None
    elif data.uid is not None:
        try:
            user_obj = pwd.getpwuid(data.uid, as_dict=True)
        except KeyError:
            raise KeyError(f"{data.uid}: user with this id does not exist") from None
    else:
        raise ValueError('Either "username" or "uid" must be specified')

    if (source := NSS_SOURCES.get(user_obj["source"])) is None:
        context.logger.error("%s: unknown ID source.", user_obj["source"])
        raise ValueError(f"{user_obj['source']}: unknown ID source. Please file a bug report.")

    grouplist: list[int] | None = None
    if data.get_groups:
        grouplist = os.getgrouplist(user_obj["pw_name"], user_obj["pw_gid"])

    sid: str | None = None
    if data.sid_info:
        sid = _get_sid(context, user_obj, source)

    return UserGetUserObjData(
        pw_name=user_obj["pw_name"],
        pw_gecos=user_obj["pw_gecos"],
        pw_dir=user_obj["pw_dir"],
        pw_shell=user_obj["pw_shell"],
        pw_uid=user_obj["pw_uid"],
        pw_gid=user_obj["pw_gid"],
        grouplist=grouplist,
        sid=sid,
        source=source,
        local=source == "LOCAL",
    )


def _get_sid(context: ServiceContext, user_obj: PasswdDict, source: NssSource) -> str | None:
    sid: str | None = None
    idmap_ctx: Any
    match source:
        case "LOCAL":
            idmap_ctx = None
            db_entry = context.call_sync2(
                context.s.user.query,
                [["username", "=", user_obj["pw_name"]], ["local", "=", True]],
                QueryOptions(select=["sid"]),
            )
            if not db_entry:
                context.logger.error(
                    "%s: local user exists on server but does not exist in the the user account table.",
                    user_obj["pw_name"],
                )
            else:
                sid = db_entry[0].sid
        case "ACTIVEDIRECTORY":
            # winbind provides idmapping for AD users
            try:
                idmap_ctx = idmap_winbind.WBClient()  # type: ignore[no-untyped-call]
            except wbclient.WBCError as e:
                # Library error from libwbclient.
                # Don't bother logging if winbind isn't running since
                # we have plenty of other places that are logging that
                # error condition
                if e.error_code != wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE:
                    context.logger.error(
                        "Failed to retrieve SID for uid: %d",
                        user_obj["pw_uid"],
                        exc_info=True,
                    )

                idmap_ctx = None
        case _:
            # SSSD provides ID mapping for IPA domains
            idmap_ctx = idmap_sss.SSSClient()

    if idmap_ctx is not None:
        try:
            sid = idmap_ctx.uidgid_to_idmap_entry(
                {
                    "id_type": "USER",
                    "id": user_obj["pw_uid"],
                }
            )["sid"]
        except MatchNotFound:
            # This is a more odd situation. Most likely case is that the user account exists
            # in IPA but doesn't have a SID assigned to it. All AD users have SIDs.
            sid = None

    return sid
