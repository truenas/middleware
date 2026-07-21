from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import and_, types
from sqlalchemy.sql import sqltypes

from middlewared.service import Service
from middlewared.sqlalchemy import Model

from .filter import FilterMixin
from .schema import SchemaMixin

"""
By default, when an update/insert/delete operation occurs we will
emit an event via our event plugin to be processed for the webui.
This is important, for example, when a new disk is inserted/removed.
In either of the above scenarios, the webUI will process this event
and update the front-end accordingly. It negates the front-end having
to poll the backend (which is expensive). However, on very large
systems (i.e. systems with 100+ disks) emitting an event can become absurdly
expensive. This reason why this becomes expensive is because for every
db operation, we run the plugins associated "query" method. So if we
update 1000 table entries, then we run "disk.query" 1000 times. In
real world testing, this has shown to take roughly 82 seconds to update
100 entries on the `storage_disk` table when there are 641 entries total.
The database was on a NVMe disk. The solution to this is adding the
`send_events` key. If this is set to False, then an event will not be
sent for the db operation. It is the callers responsibility to emit an event
after all the db operations are complete.
"""


@dataclass(slots=True, kw_only=True)
class DatastoreOptions:
    cascade: bool = False
    ha_sync: bool = True
    prefix: str = ""
    send_events: bool = True


class NoRowsWereUpdatedException(Exception):
    pass


class DatastoreService(Service, FilterMixin, SchemaMixin):

    class Config:
        private = True

    def _handle_datastore_opts(self, options: dict | None = None):
        if options is None:
            opts = asdict(DatastoreOptions())
        else:
            opts = asdict(DatastoreOptions(**options))
        return opts

    async def insert(self, name: str, data: dict, options: dict | None = None):
        """
        Insert a new entry to `name`.
        """
        table = self._get_table(name)
        options = self._handle_datastore_opts(options)
        insert, relationships = self._extract_relationships(table, options['prefix'], data)
        for column in table.c:
            if column.default is not None:
                value = column.default.arg
                if callable(value):
                    value = value(None)
                insert.setdefault(column.name, value)
            if not column.nullable:
                if isinstance(column.type, (types.String, types.Text)):
                    insert.setdefault(column.name, '')

        pk_column = self._get_pk(table)
        # Only use last_insert_rowid if the PK is an integer type AND we didn't provide a value
        return_last_insert_rowid = (
            isinstance(pk_column.type, sqltypes.Integer) and
            pk_column.name not in insert
        )
        result = await self.middleware.call(
            'datastore.execute_write',
            table.insert().values(**insert),
            {
                'ha_sync': options['ha_sync'],
                'return_last_insert_rowid': return_last_insert_rowid,
            },
        )
        if return_last_insert_rowid:
            pk = result
        else:
            pk = insert[pk_column.name]

        try:
            await self._handle_relationships(pk, relationships)
        except Exception:
            await self.middleware.call(
                'datastore.execute_write',
                table.delete().where(pk_column == pk),
                {
                    'ha_sync': options['ha_sync'],
                },
            )
            raise

        if options['send_events']:
            await self.middleware.call('datastore.send_insert_events', name, insert)

        return pk

    async def update(self, name: str, id_or_filters: Any, data: dict, options: dict | None = None):
        """
        Update an entry `id` in `name`.
        """
        table = self._get_table(name)
        data = data.copy()
        options = self._handle_datastore_opts(options)
        if isinstance(id_or_filters, list):
            rows = await self.middleware.call('datastore.query', name, id_or_filters, {'prefix': options['prefix']})
            if len(rows) != 1:
                raise RuntimeError(f'{len(rows)} found, expecting one')

            id_ = rows[0][self._get_pk(table).name]
        else:
            id_ = id_or_filters

        for column in table.c:
            if column.foreign_keys:
                if column.name[:-3] in data:
                    data[column.name] = data.pop(column.name[:-3])

        update, relationships = self._extract_relationships(table, options['prefix'], data)

        if update:
            result = await self.middleware.call(
                'datastore.execute_write',
                table.update().values(**update).where(self._where_clause(table, id_, {'prefix': options['prefix']})),
                {
                    'ha_sync': options['ha_sync'],
                },
            )
            if result.rowcount != 1:
                raise NoRowsWereUpdatedException()

            if options['send_events']:
                await self.middleware.call('datastore.send_update_events', name, id_)

        await self._handle_relationships(id_, relationships)

        return id_

    def _extract_relationships(self, table, prefix, data):
        relationships = self._get_relationships(table)

        insert = {}
        insert_relationships = []
        for k, v in data.items():
            relationship = relationships.get(prefix + k)
            if relationship:
                insert_relationships.append((relationship, v))
            else:
                insert[self._get_col(table, k, prefix).name] = v

        return insert, insert_relationships

    async def _handle_relationships(self, pk, relationships):
        for relationship, values in relationships:
            assert len(relationship.synchronize_pairs) == 1
            assert len(relationship.secondary_synchronize_pairs) == 1

            local_pk, relationship_local_pk = relationship.synchronize_pairs[0]
            remote_pk, relationship_remote_pk = relationship.secondary_synchronize_pairs[0]

            await self.middleware.call(
                'datastore.execute_write',
                relationship_local_pk.table.delete().where(relationship_local_pk == pk)
            )

            for value in values:
                await self.middleware.call(
                    'datastore.execute_write',
                    relationship_local_pk.table.insert().values({
                        relationship_local_pk.name: pk,
                        relationship_remote_pk.name: value,
                    })
                )

    def _where_clause(self, table, id_or_filters, options):
        if isinstance(id_or_filters, list):
            return and_(*self._filters_to_queryset(id_or_filters, table, options['prefix'], {}))
        else:
            return self._get_pk(table) == id_or_filters

    async def delete(self, name: str, id_or_filters: Any, options: dict | None = None):
        """
        Delete an entry `id` in `name`.
        """
        table = self._get_table(name)
        options = self._handle_datastore_opts(options)

        if options['cascade']:
            if not isinstance(id_or_filters, int):
                raise ValueError('Cascade delete is only supported when deleting a single row by its id')

            await self._cascade_delete(table, id_or_filters, options)

        await self.middleware.call(
            'datastore.execute_write',
            table.delete().where(self._where_clause(table, id_or_filters, {'prefix': options['prefix']})),
            {
                'ha_sync': options['ha_sync'],
            },
        )

        if not isinstance(id_or_filters, list) and options['send_events']:
            await self.middleware.call('datastore.send_delete_events', name, id_or_filters)

        return True

    async def _cascade_delete(self, table, id_: int, options: dict):
        """
        Delete the rows that reference (via a foreign key) the row `id_` of `table` that is about to be deleted.
        """
        pk = self._get_pk(table)
        child_options = {
            'cascade': True,
            'ha_sync': options['ha_sync'],
            'send_events': options['send_events'],
        }
        for referencing_table in Model.metadata.tables.values():
            for column in referencing_table.c:
                if not any(foreign_key.column is pk for foreign_key in column.foreign_keys):
                    continue

                referencing_name = referencing_table.name.replace('_', '.', 1)
                referencing_pk_name = self._get_pk(referencing_table).name
                for row in await self.middleware.call(
                    'datastore.query',
                    referencing_name,
                    [[column.name, '=', id_]],
                    {'relationships': False},
                ):
                    referencing_id = row[referencing_pk_name]
                    self.middleware.logger.warning(
                        '%s: cascade deleting row %r referencing %s row %r',
                        referencing_table.name, referencing_id, table.name, id_,
                    )
                    await self.delete(referencing_name, referencing_id, child_options)
