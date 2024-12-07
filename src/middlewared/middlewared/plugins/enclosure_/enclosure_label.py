import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    EnclosureLabelDeleteArgs,
    EnclosureLabelDeleteResult,
    EnclosureLabelEntry,
    EnclosureLabelUpdateArgs,
    EnclosureLabelUpdateResult,
)
from middlewared.service import CRUDService


class EnclosureLabelModel(sa.Model):
    __tablename__ = "enclosure_label"
    id = sa.Column(sa.String(200), primary_key=True)
    label = sa.Column(sa.String(200))


class EnclosureLabelService(CRUDService):
    class Config:
        datastore = "enclosure.label"
        namespace = "enclosure.label"
        cli_private = True
        entry = EnclosureLabelEntry

    @api_method(EnclosureLabelUpdateArgs, EnclosureLabelUpdateResult)
    async def do_update(self, data):
        await self.get_instance(data["id"])
        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            data["id"],
            {"label": data["label"]},
        )
        return await self.get_instance(data["id"])

    @api_method(EnclosureLabelDeleteArgs, EnclosureLabelDeleteResult)
    async def do_delete(self, data):
        await self.middleware.call("datastore.delete", data["id"])
