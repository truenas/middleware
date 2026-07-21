from __future__ import annotations

from typing import Any

from middlewared.api.current import MailEntry, MailUpdate
from middlewared.service import ConfigServicePart, ValidationError
import middlewared.sqlalchemy as sa

from .gmail import gmail


class MailModel(sa.Model):
    __tablename__ = "system_email"

    id = sa.Column(sa.Integer(), primary_key=True)
    em_fromemail = sa.Column(sa.String(120))
    em_outgoingserver = sa.Column(sa.String(120))
    em_port = sa.Column(sa.Integer(), default=25)
    em_security = sa.Column(sa.String(120), default="PLAIN")
    em_smtp = sa.Column(sa.Boolean())
    em_user = sa.Column(sa.String(120), nullable=True)
    em_pass = sa.Column(sa.EncryptedText(), nullable=True)
    em_fromname = sa.Column(sa.String(120))
    em_oauth = sa.Column(sa.JSON(dict, encrypted=True), nullable=True)


def validate_config(data: MailEntry) -> None:
    if data.smtp and not data.user:
        raise ValidationError("user", "This field is required when SMTP authentication is enabled")

    oauth = data.oauth.get_secret_value()
    if not oauth or oauth.provider == "outlook":
        if not data.fromemail:
            raise ValidationError("fromemail", "This field is required")

    password = data.pass_.get_secret_value()
    if password:
        # FIXME: smtplib does not support non-ascii password yet
        # https://github.com/python/cpython/pull/8938
        try:
            password.encode("ascii")
        except UnicodeEncodeError:
            raise ValidationError(
                "pass",
                "Only plain text characters (7-bit ASCII) are allowed in passwords. "
                "UTF or composed characters are not allowed.",
            )


class MailConfigServicePart(ConfigServicePart[MailEntry]):
    _datastore = "system.email"
    _datastore_prefix = "em_"
    _entry = MailEntry

    def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        if not data["oauth"]:
            data["oauth"] = None

        return data

    async def do_update(self, data: MailUpdate) -> MailEntry:
        old = await self.config()
        new = old.updated(data)

        validate_config(new)

        await self._update(new)

        await self.middleware.run_in_thread(gmail.initialize, self)
        await self.call2(self.s.alert.oneshot_delete, "GMailConfigurationDiscarded", None)

        return await self.config()
