import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import EnclosureLabelUpdateArgs, EnclosureLabelUpdateResult
from middlewared.service import private, Service


class EnclosureLabelModel(sa.Model):
    __tablename__ = "enclosure_label"

    id = sa.Column(sa.Integer(), primary_key=True)
    encid = sa.Column(sa.String(200), unique=True)
    label = sa.Column(sa.String(200))


class EnclosureService(Service):
    class Config:
        namespace = "enclosure"
        cli_namespace = "storage.enclosure"

    @api_method(EnclosureLabelUpdateArgs, EnclosureLabelUpdateResult)
    async def update(self, id_, data):
        if "label" in data:
            await self.middleware.call(
                "datastore.delete", "enclosure.label", [["encid", "=", id_]]
            )
            await self.middleware.call(
                "datastore.insert",
                "enclosure.label",
                {"encid": id_, "label": data["label"]},
            )

    @private
    async def get_labels(self):
        return {
            label["encid"]: label["label"]
            for label in await self.middleware.call("datastore.query", "enclosure.label")
        }
