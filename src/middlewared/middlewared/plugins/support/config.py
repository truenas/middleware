from middlewared.api.current import SupportEntry, SupportUpdate
from middlewared.service import ConfigServicePart, ValidationErrors
import middlewared.sqlalchemy as sa


class SupportModel(sa.Model):
    __tablename__ = "system_support"

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), nullable=True, default=True)
    name = sa.Column(sa.String(200))
    title = sa.Column(sa.String(200))
    email = sa.Column(sa.String(200))
    phone = sa.Column(sa.String(200))
    secondary_name = sa.Column(sa.String(200))
    secondary_title = sa.Column(sa.String(200))
    secondary_email = sa.Column(sa.String(200))
    secondary_phone = sa.Column(sa.String(200))


class SupportConfigServicePart(ConfigServicePart[SupportEntry]):
    _datastore = "system.support"
    _entry = SupportEntry

    async def do_update(self, data: SupportUpdate) -> SupportEntry:
        new = (await self.config()).updated(data)
        self.validate(new)
        await self._update(new)
        return await self.config()

    def validate(self, data: SupportEntry, schema: str = "support_update") -> None:
        verrors = ValidationErrors()
        if data.enabled:
            for key in ("name", "title", "email", "phone"):
                for prefix in ("", "secondary_"):
                    field = prefix + key
                    if not getattr(data, field):
                        verrors.add(f"{schema}.{field}", "This field is required")
        verrors.check()
