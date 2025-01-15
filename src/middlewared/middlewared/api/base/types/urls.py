from typing import Annotated

from pydantic import AfterValidator, HttpUrl

from middlewared.api.base.validators import https_only_check


HttpsOnlyURL = Annotated[HttpUrl, AfterValidator(https_only_check)]
