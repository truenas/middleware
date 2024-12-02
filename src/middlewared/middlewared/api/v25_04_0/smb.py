from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    single_argument_args,
    SID,
)
from pydantic import Field, model_validator
from typing import Literal, Self

__all__ = [
    'GetSmbAclArgs', 'GetSmbAclResult',
    'SetSmbAclArgs', 'SetSmbAclResult',
]


class SMBShareAclEntryWhoId(BaseModel):
    id_type: Literal['USER', 'GROUP', 'BOTH']
    xid: int = Field(alias='id')


class SMBShareAclEntry(BaseModel):
    ae_perm: Literal['FULL', 'CHANGE', 'READ']
    """ Permissions granted to the principal. """
    ae_type: Literal['ALLOWED', 'DENIED']
    """ The type of SMB share ACL entry. """
    ae_who_sid: SID | None = None
    """ SID value of principle for whom ACL entry applies. """
    ae_who_id: SMBShareAclEntryWhoId | None = None
    """ Unix ID of principle for whom ACL entry applies. """
    ae_who_str: NonEmptyString | None = None

    @model_validator(mode='after')
    def check_ae_who(self) -> Self:
        if self.ae_who_sid is None and self.ae_who_id is None and self.ae_who_str is None:
            raise ValueError(
                'Either ae_who_sid or ae_who_id or ae_who_str is required to identify user or group '
                'to which the ACL entry applies.'
            )

        return self


class SMBShareAcl(BaseModel):
    share_name: NonEmptyString
    """ Name of the SMB share. """
    share_acl: list[SMBShareAclEntry] = [SMBShareAclEntry(ae_who_sid='S-1-1-0', ae_perm='FULL', ae_type='ALLOWED')]
    """ List of SMB share ACL entries """


@single_argument_args('smb_setacl')
class SetSmbAclArgs(SMBShareAcl):
    pass


class SetSmbAclResult(BaseModel):
    result: SMBShareAcl


@single_argument_args('smb_getacl')
class GetSmbAclArgs(BaseModel):
    share_name: NonEmptyString


class GetSmbAclResult(SetSmbAclResult):
    pass
