from __future__ import annotations

from middlewared.api.current import WebshareEntry, WebshareUpdate
from middlewared.service import ConfigServicePart, ValidationError
import middlewared.sqlalchemy as sa

from .utils import bindip_choices as get_bindip_choices


class WebshareModel(sa.Model):
    __tablename__ = "services_webshare"

    id = sa.Column(sa.Integer(), primary_key=True)
    bindip = sa.Column(sa.JSON(list), default=[])
    search = sa.Column(sa.Boolean(), default=False)
    passkey = sa.Column(sa.String(20), default="DISABLED")
    groups = sa.Column(sa.JSON(list), default=[])


class WebshareConfigPart(ConfigServicePart[WebshareEntry]):
    _datastore = "services.webshare"
    _entry = WebshareEntry

    async def do_update(self, data: WebshareUpdate) -> WebshareEntry:
        old = await self.config()
        new = old.updated(data)

        bindip_choices = await get_bindip_choices(self)
        for i, bindip in enumerate(new.bindip):
            if bindip not in bindip_choices:
                raise ValidationError(
                    f"bindip.{i}", f"Cannot use {bindip}. Please provide a valid ip address."
                )

        if new.groups:
            if not (await self.middleware.call("system.general.config"))["ds_auth"]:
                raise ValidationError("groups", "Directory Service authentication is disabled.")
            else:
                groups: list[str] = []
                for i, group in enumerate(new.groups):
                    try:
                        group_obj = await self.middleware.call(
                            "group.get_group_obj", {"groupname": group}
                        )
                    except KeyError:
                        raise ValidationError(f"groups.{i}", f"{group}: group does not exist.")
                    else:
                        if group_obj["local"]:
                            raise ValidationError(
                                f"groups.{i}",
                                f"{group}: group must be an Directory Service group."
                            )
                        groups.append(group_obj["gr_name"])
                new.groups = groups

        await self.middleware.call(
            "datastore.update", self._datastore, new.id, new.model_dump()
        )
        return new
