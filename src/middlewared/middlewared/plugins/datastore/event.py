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
        Dict("extra", additional_attrs=True),
        Str("id", default="id"),
        Str("process_event", null=True, default=None),
        strict=True,
    ))
    async def register_event(self, options):
        self.events[options["datastore"]].append(options)

        self.middleware.event_register(f"{options['plugin']}.query", options["description"])

    async def send_insert_events(self, datastore, row):
        for options in self.events[datastore]:
            await self._send_event(
                options,
                "ADDED",
                id=row[options["prefix"] + options["id"]],
                fields=await self._fields(options, row),
            )

    async def send_update_events(self, datastore, id):
        for options in self.events[datastore]:
            fields = await self._fields(options, {options["prefix"] + options["id"]: id}, False)
            if not fields:
                # It is possible the row in question got deleted with the update
                # event still pending, in this case we skip sending update event
                continue

            await self._send_event(
                options,
                "CHANGED",
                id=id,
                fields=fields[0],
            )

    async def send_delete_events(self, datastore, id):
        for options in self.events[datastore]:
            await self._send_event(
                options,
                "CHANGED",
                id=id,
                cleared=True,
            )

    async def _fields(self, options, row, get=True):
        query_options = {"get": get}
        if options.get("extra"):
            query_options["extra"] = options["extra"]

        return await self.middleware.call(
            f"{options['plugin']}.query",
            [[options["id"], "=", row[options["prefix"] + options["id"]]]],
            query_options,
        )

    async def _send_event(self, options, type, **kwargs):
        if options["process_event"]:
            processed = await self.middleware.call(options["process_event"], type, kwargs)
            if processed is None:
                return

            type, kwargs = processed

        self.middleware.send_event(
            f"{options['plugin']}.query",
            type,
            **kwargs,
        )
