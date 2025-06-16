import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import EnclosureLabelSetArgs, EnclosureLabelSetResult
from middlewared.service import private, Service
from middlewared.service_exception import MatchNotFound, ValidationError


class EnclosureLabelModel(sa.Model):
    __tablename__ = "enclosure_label"

    id = sa.Column(sa.Integer(), primary_key=True)
    encid = sa.Column(sa.String(200), unique=True)
    label = sa.Column(sa.String(200))


class EnclosureLabelService(Service):
    class Config:
        namespace = "enclosure.label"
        cli_namespace = "storage.enclosure.label"

    @private
    async def get_all(self):
        return {
            label["encid"]: label["label"]
            for label in await self.middleware.call("datastore.query", "enclosure.label")
        }

    @api_method(EnclosureLabelSetArgs, EnclosureLabelSetResult, roles=["ENCLOSURE_WRITE"])
    async def set(self, id_, label):
        try:
            await self.middleware.call("enclosure2.query", [["id", "=", id_]], {"get": True})
        except MatchNotFound:
            raise ValidationError("id", f'Enclosure with id: {id_!r} not found')

        await self.middleware.call(
            "datastore.delete", "enclosure.label", [["encid", "=", id_]]
        )
        await self.middleware.call(
            "datastore.insert",
            "enclosure.label",
            {"encid": id_, "label": label},
        )
