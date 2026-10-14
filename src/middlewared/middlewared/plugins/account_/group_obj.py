from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import wbclient

from middlewared.api.current import GroupGetGroupObj, GroupGetGroupObjData, QueryOptions
from middlewared.plugins.idmap_ import idmap_sss, idmap_winbind
from middlewared.service import ValidationErrors
from middlewared.service_exception import MatchNotFound
from middlewared.utils.nss import grp
from middlewared.utils.nss.grp import GroupDict
from middlewared.utils.nss.nss_common import NssModule

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

NssSource = Literal["LOCAL", "ACTIVEDIRECTORY", "LDAP"]

NSS_SOURCES: dict[str, NssSource] = {
    NssModule.FILES.name: "LOCAL",
    NssModule.WINBIND.name: "ACTIVEDIRECTORY",
    NssModule.SSS.name: "LDAP",
}


def get_group_obj(context: ServiceContext, data: GroupGetGroupObj) -> GroupGetGroupObjData:
    verrors = ValidationErrors()
    if not data.groupname and data.gid is None:
        verrors.add("get_group_obj.groupname", 'Either "groupname" or "gid" must be specified')
    if data.groupname and data.gid is not None:
        verrors.add("get_group_obj.groupname", '"groupname" and "gid" may not be simultaneously specified')
    verrors.check()

    # NOTE: per request from UI team we are overriding default library
    # KeyError message with a clearer one
    #
    # Many callers to group.get_group_obj may be catching KeyError and so
    # changing exception type is something that should be approached
    # carefully.
    if data.groupname:
        try:
            grp_obj: GroupDict = grp.getgrnam(data.groupname, as_dict=True)
        except KeyError:
            raise KeyError(f"{data.groupname}: group with this name does not exist") from None
    elif data.gid is not None:
        try:
            grp_obj = grp.getgrgid(data.gid, as_dict=True)
        except KeyError:
            raise KeyError(f"{data.gid}: group with this id does not exist") from None
    else:
        raise ValueError('Either "groupname" or "gid" must be specified')

    if (source := NSS_SOURCES.get(grp_obj["source"])) is None:
        context.logger.error("%s: unknown ID source.", grp_obj["source"])
        raise ValueError(f"{grp_obj['source']}: unknown ID source. Please file a bug report.")

    sid: str | None = None
    if data.sid_info:
        sid = _get_sid(context, grp_obj, source)

    return GroupGetGroupObjData(
        gr_name=grp_obj["gr_name"],
        gr_gid=grp_obj["gr_gid"],
        gr_mem=grp_obj["gr_mem"],
        sid=sid,
        source=source,
        local=source == "LOCAL",
    )


def _get_sid(context: ServiceContext, grp_obj: GroupDict, source: NssSource) -> str | None:
    sid: str | None = None
    idmap_ctx: Any
    match source:
        case "LOCAL":
            idmap_ctx = None
            db_entry = context.call_sync2(
                context.s.group.query,
                [["group", "=", grp_obj["gr_name"]], ["local", "=", True]],
                QueryOptions(select=["sid"]),
            )
            if not db_entry:
                context.logger.error(
                    "%s: local group exists on server but does not exist in the the group account table.",
                    grp_obj["gr_name"],
                )
            else:
                sid = db_entry[0].sid
        case "ACTIVEDIRECTORY":
            # winbind provides idmapping for AD groups
            try:
                idmap_ctx = idmap_winbind.WBClient()  # type: ignore[no-untyped-call]
            except wbclient.WBCError as e:
                # Library error from libwbclient.
                # Don't bother logging if winbind isn't running since
                # we have plenty of other places that are logging that
                # error condition
                if e.error_code != wbclient.WBC_ERR_WINBIND_NOT_AVAILABLE:
                    context.logger.error(
                        "Failed to retrieve SID for gid: %d",
                        grp_obj["gr_gid"],
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
                    "id_type": "GROUP",
                    "id": grp_obj["gr_gid"],
                }
            )["sid"]
        except MatchNotFound:
            # This can happen if IPA and group doesn't have SID assigned
            sid = None

    return sid
