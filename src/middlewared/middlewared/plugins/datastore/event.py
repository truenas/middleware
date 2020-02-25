from collections import defaultdict

from middlewared.schema import accepts, Dict, Str
from middlewared.service import Service


class DatastoreService(Service):

    class Config:
        private = True

    events = defaultdict(list)

    @accepts(Dict(
        "options",
        Str("description", required=True),
        Str("datastore", required=True),
        Str("plugin", required=True),
        Str("prefix", default=""),
        Str("id", default="id"),
        strict=True,
    ))
    async def register_event(self, options):
        self.events[options["datastore"]].append(options)

        self.middleware.event_register(f"{options['plugin']}.query", options["description"])

    async def send_insert_events(self, datastore, row):
        for options in self.events[datastore]:
            self.middleware.send_event(
                f"{options['plugin']}.query",
                "ADDED",
                id=row[options["prefix"] + options["id"]],
                fields=await self._fields(options, row),
            )

    async def send_update_events(self, datastore, row):
        for options in self.events[datastore]:
            fields = await self._fields(options, row, False)
            if not fields:
                # It is possible the row in question got deleted with the update
                # event still pending, in this case we skip sending update event
                continue
            self.middleware.send_event(
                f"{options['plugin']}.query",
                "CHANGED",
                id=row[options["prefix"] + options["id"]],
                fields=fields[0],
            )

    async def send_delete_events(self, datastore, id):
        for options in self.events[datastore]:
            self.middleware.send_event(
                f"{options['plugin']}.query",
                "CHANGED",
                id=id,
                cleared=True,
            )

    async def _fields(self, options, row, get=True):
        return await self.middleware.call(
            f"{options['plugin']}.query",
            [[options["id"], "=", row[options["prefix"] + options["id"]]]],
            {"get": get},
        )
