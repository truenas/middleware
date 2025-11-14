from dataclasses import asdict, dataclass, field
from collections import defaultdict

from middlewared.service import Service


@dataclass(slots=True, kw_only=True)
class DatastoreRegisterEventArgs:
    datastore: str
    plugin: str
    prefix: str = ""
    extra: dict = field(default_factory=dict)
    id: str = "id"
    process_event: str | None = None


class DatastoreService(Service):

    class Config:
        private = True

    events = defaultdict(list)

    async def register_event(self, options: dict) -> None:
        options = asdict(DatastoreRegisterEventArgs(**options))
        self.events[options["datastore"]].append(options)

    async def send_insert_events(self, datastore, row):
        for options in self.events[datastore]:
            await self._send_event(
                options,
                "ADDED",
                id=row[options["prefix"] + options["id"]],
                fields=await self._fields(options, row),
            )

    async def send_update_events(self, datastore, id_):
        for options in self.events[datastore]:
            fields = await self._fields(options, {options["prefix"] + options["id"]: id_}, False)
            if not fields:
                # It is possible the row in question got deleted with the update
                # event still pending, in this case we skip sending update event
                continue

            await self._send_event(
                options,
                "CHANGED",
                id=id_,
                fields=fields[0],
            )

    async def send_delete_events(self, datastore, id_):
        for options in self.events[datastore]:
            await self._send_event(options, "REMOVED", id=id_)

    async def _fields(self, options, row, get=True):
        query_options = {"get": get}
        if options.get("extra"):
            query_options["extra"] = options["extra"]

        return await self.middleware.call(
            f"{options['plugin']}.query",
            [[options["id"], "=", row[options["prefix"] + options["id"]]]],
            query_options,
        )

    async def _send_event(self, options, type_, **kwargs):
        if options["process_event"]:
            processed = await self.middleware.call(options["process_event"], type_, kwargs)
            if processed is None:
                return

            type_, kwargs = processed

        self.middleware.send_event(
            f"{options['plugin']}.query",
            type_,
            **kwargs,
        )
