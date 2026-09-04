"""Grant lists, shared by buckets and the service's global grants.

The datastore holds a grant as a row of three keys. Everything past the
two functions that read those rows, `grant_principals` and
`label_grants`, works on the API's grant models.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING, TypedDict

from middlewared.api.current import S3Access, S3Grant, S3GrantEntry, S3PrincipalType
from middlewared.service import ValidationErrors

if TYPE_CHECKING:
    from middlewared.main import Middleware


class GrantRow(TypedDict):
    """A grant as the datastore's JSON column holds it: what `compress`
    writes from an `S3Grant`, with no name."""

    principal_type: S3PrincipalType
    xid: int | None
    access: S3Access


@dataclass(frozen=True, slots=True, kw_only=True)
class Principals:
    """The uids and gids a set of grants names."""

    uids: frozenset[int]
    gids: frozenset[int]

    def __or__(self, other: Principals) -> Principals:
        return Principals(uids=self.uids | other.uids, gids=self.gids | other.gids)


@dataclass(frozen=True, slots=True, kw_only=True)
class PrincipalNames:
    """The current name of every principal a query's rows name, resolved
    once each through NSS, which is what the daemon will resolve them
    through too. An id that does not resolve is absent; it reads as its
    number, since a display label the daemon never matches on must not
    fail the row."""

    users: Mapping[int, str]
    groups: Mapping[int, str]

    def user(self, uid: int) -> str:
        return self.users.get(uid, str(uid))

    def group(self, gid: int) -> str:
        return self.groups.get(gid, str(gid))

    def label(self, principal_type: S3PrincipalType, xid: int | None) -> str:
        """A grant's display name: the account's, or its number; empty for
        everyone, who has neither."""
        if principal_type == "USER" and xid is not None:
            return self.user(xid)
        if principal_type == "GROUP" and xid is not None:
            return self.group(xid)
        return ""


async def principal_names(middleware: Middleware, principals: Principals) -> PrincipalNames:
    users: dict[int, str] = {}
    for uid in principals.uids:
        try:
            users[uid] = (await middleware.call("user.get_user_obj", {"uid": uid}))["pw_name"]
        except KeyError:
            pass
    groups: dict[int, str] = {}
    for gid in principals.gids:
        try:
            groups[gid] = (await middleware.call("group.get_group_obj", {"gid": gid}))["gr_name"]
        except KeyError:
            pass
    return PrincipalNames(users=users, groups=groups)


def grant_principals(rows: Iterable[GrantRow | Mapping[str, Any]]) -> Principals:
    """The uids and gids a stored grant list names."""
    uids = {row["xid"] for row in rows if row["principal_type"] == "USER" and row["xid"] is not None}
    gids = {row["xid"] for row in rows if row["principal_type"] == "GROUP" and row["xid"] is not None}
    return Principals(uids=frozenset(uids), gids=frozenset(gids))


def label_grants(rows: Iterable[GrantRow | Mapping[str, Any]], names: PrincipalNames) -> list[S3GrantEntry]:
    """The stored grants as entries, each carrying its principal's current
    name for display. The daemon never matches on the name; the xid is the
    identity."""
    return [
        S3GrantEntry.model_validate({**row, "name": names.label(row["principal_type"], row["xid"])}) for row in rows
    ]


def grant_label(grant: S3GrantEntry) -> str:
    """The quoted NAME of a rendered grant heading. A label the daemon never
    resolves, but a quote inside it breaks the heading grammar and an empty
    one is refused, either of which refuses the whole load."""
    label = grant.name.replace('"', "").replace("\n", "").replace("\r", "").strip()
    return label or str(grant.xid)


async def validate_grants(
    middleware: Middleware, schema: str, grants: Sequence[S3Grant], verrors: ValidationErrors
) -> None:
    seen: set[tuple[S3PrincipalType, int | None]] = set()
    for i, grant in enumerate(grants):
        principal_type, xid = grant.principal_type, grant.xid
        if principal_type == "EVERYONE":
            if xid is not None:
                verrors.add(f"{schema}.{i}.xid", "xid is not allowed for an EVERYONE grant.")
        elif xid is None:
            verrors.add(f"{schema}.{i}.xid", f"xid is required for a {principal_type} grant.")
        elif principal_type == "USER":
            try:
                await middleware.call("user.get_user_obj", {"uid": xid})
            except KeyError:
                verrors.add(f"{schema}.{i}.xid", f"No user with uid {xid} exists.")
        else:
            try:
                await middleware.call("group.get_group_obj", {"gid": xid})
            except KeyError:
                verrors.add(f"{schema}.{i}.xid", f"No group with gid {xid} exists.")

        key = (principal_type, xid)
        if key in seen:
            verrors.add(f"{schema}.{i}", "The same principal may only be granted once.")
        seen.add(key)
