from typing import Annotated

from pydantic import AfterValidator, HttpUrl

from middlewared.api.base.validators import https_only_check

__all__ = ["HttpsOnlyURL"]


HttpsOnlyURL = Annotated[HttpUrl, AfterValidator(https_only_check)]
