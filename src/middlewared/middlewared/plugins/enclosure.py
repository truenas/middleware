import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Dict, Str
from middlewared.service import CRUDService


class EnclosureLabelModel(sa.Model):
    __tablename__ = "truenas_enclosurelabel"

    id = sa.Column(sa.Integer(), primary_key=True)
    encid = sa.Column(sa.String(200), unique=True)
    label = sa.Column(sa.String(200))


class EnclosureService(CRUDService):
    class Config:
        cli_namespace = "storage.enclosure"

    @accepts(
        Str("id"),
        Dict(
            "enclosure_update",
            Str("label"),
            update=True,
        ),
    )
    async def do_update(self, id_, data):
        if "label" in data:
            await self.middleware.call(
                "datastore.delete", "truenas.enclosurelabel", [["encid", "=", id_]]
            )
            await self.middleware.call(
                "datastore.insert",
                "truenas.enclosurelabel",
                {"encid": id_, "label": data["label"]},
            )
        return await self.get_instance(id_)
