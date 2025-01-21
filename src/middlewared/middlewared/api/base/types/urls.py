from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, HttpUrl

from middlewared.api.base.validators import https_only_check

__all__ = ["HttpsOnlyURL", "HttpVerb"]


HttpsOnlyURL = Annotated[HttpUrl, AfterValidator(https_only_check)]

HttpVerb: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "CALL", "SUBSCRIBE", "*"]
