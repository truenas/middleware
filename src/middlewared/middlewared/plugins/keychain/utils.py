from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Literal, overload

from middlewared.api.current import SSHCredentialsEntry, SSHKeyPairEntry
from middlewared.service_exception import CallError, MatchNotFound

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


@overload
async def get_of_type(
    context: ServiceContext,
    id_: int,
    type_: Literal["SSH_KEY_PAIR"],
) -> SSHKeyPairEntry: ...
@overload
async def get_of_type(
    context: ServiceContext,
    id_: int,
    type_: Literal["SSH_CREDENTIALS"],
) -> SSHCredentialsEntry: ...
async def get_of_type(
    context: ServiceContext,
    id_: int,
    type_: Literal["SSH_KEY_PAIR", "SSH_CREDENTIALS"],
) -> SSHKeyPairEntry | SSHCredentialsEntry:
    try:
        credential = await context.middleware.call(
            "datastore.query", "system.keychaincredential", [["id", "=", id_]], {"get": True}
        )
    except MatchNotFound:
        raise CallError("Credential does not exist", errno.ENOENT)

    if credential["type"] != type_:
        raise CallError(f"Credential is not of type {type_}", errno.EINVAL)

    if not credential["attributes"]:
        raise CallError(f"Decrypting credential {credential['name']} failed", errno.EFAULT)

    if type_ == "SSH_KEY_PAIR":
        return SSHKeyPairEntry.model_validate(credential)
    else:
        return SSHCredentialsEntry.model_validate(credential)
