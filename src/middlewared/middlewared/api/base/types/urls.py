from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, HttpUrl, PlainSerializer

from middlewared.api.base.validators import https_only_check

__all__ = ["HttpsOnlyURL", "HttpVerb"]


# `AfterValidator` keeps the field as an `HttpUrl` so the annotation matches the
# stored value; `PlainSerializer(str)` ensures `model_dump()` emits a plain
# string in both `python` and `json` modes so downstream consumers (WebSocket
# JSON encoding, `urllib.parse.urljoin`) don't see a `Url` object.
HttpsOnlyURL = Annotated[HttpUrl, AfterValidator(https_only_check), PlainSerializer(str, return_type=str)]

HttpVerb: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "CALL", "SUBSCRIBE", "*"]
