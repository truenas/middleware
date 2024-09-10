from middlewared.api.base import BaseModel, single_argument_result
from .user import UserGetUserObjResult


class AuthMeArgs(BaseModel):
    pass


@single_argument_result
class AuthMeResult(UserGetUserObjResult.model_fields["result"].annotation):
    attributes: dict
    two_factor_config: dict
    privilege: dict
    account_attributes: list[str]
