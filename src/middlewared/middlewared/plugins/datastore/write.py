from sqlalchemy import and_, types
from sqlalchemy.sql import sqltypes

from middlewared.schema import accepts, Any, Dict, Str
from middlewared.service import Service

from .filter import FilterMixin
from .schema import SchemaMixin


class DatastoreService(Service, FilterMixin, SchemaMixin):

    class Config:
        private = True

    @accepts(Str('name'), Dict('data', additional_attrs=True), Dict('options', Str('prefix', default='')))
    async def insert(self, name, data, options):
        """
        Insert a new entry to `name`.
        """
        table = self._get_table(name)
        insert, relationships = self._extract_relationships(table, options['prefix'], data)

        for column in table.c:
            if column.default is not None:
                insert.setdefault(column.name, column.default.arg)
            if not column.nullable:
                if isinstance(column.type, (types.String, types.Text)):
                    insert.setdefault(column.name, '')

        pk_column = self._get_pk(table)
        return_last_insert_rowid = type(pk_column.type) == sqltypes.Integer
        result = await self.middleware.call('datastore.execute_write', table.insert().values(**insert),
                                            return_last_insert_rowid)
        if return_last_insert_rowid:
            pk = result
        else:
            pk = insert[pk_column.name]

        await self._handle_relationships(pk, relationships)

        await self.middleware.call('datastore.send_insert_events', name, insert)

        return pk

    @accepts(Str('name'), Any('id_or_filters'), Dict('data', additional_attrs=True),
             Dict('options', Str('prefix', default='')))
    async def update(self, name, id_or_filters, data, options):
        """
        Update an entry `id` in `name`.
        """
        table = self._get_table(name)
        data = data.copy()

        if isinstance(id_or_filters, list):
            rows = await self.middleware.call('datastore.query', name, id_or_filters, options)
            if len(rows) != 1:
                raise RuntimeError(f'{len(rows)} found, expecting one')

            id = rows[0][self._get_pk(table).name]
        else:
            id = id_or_filters

        for column in table.c:
            if column.foreign_keys:
                if column.name[:-3] in data:
                    data[column.name] = data.pop(column.name[:-3])

        update, relationships = self._extract_relationships(table, options['prefix'], data)

        if update:
            result = await self.middleware.call(
                'datastore.execute_write',
                table.update().values(**update).where(self._where_clause(table, id, options)),
            )
            if result.rowcount != 1:
                raise RuntimeError('No rows were updated')

            await self.middleware.call('datastore.send_update_events', name, id)

        await self._handle_relationships(id, relationships)

        return id

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

    @accepts(Str('name'), Any('id_or_filters'), Dict('options', Str('prefix', default='')))
    async def delete(self, name, id_or_filters, options):
        """
        Delete an entry `id` in `name`.
        """
        table = self._get_table(name)

        await self.middleware.call(
            'datastore.execute_write',
            table.delete().where(self._where_clause(table, id_or_filters, options)),
        )

        # FIXME: Sending events for batch deletes not implemented yet
        if not isinstance(id_or_filters, list):
            await self.middleware.call('datastore.send_delete_events', name, id_or_filters)

        return True
