# datastore layer

## Basic information

FreeNAS 10 introduces database abstraction layer called "datastore". datastore is a Python module, installed globally (so it's possible to do `import datastore` anywhere inside FN10 system).

Data is stored as JSON object in "schemaless" manner. "object" is a python dict() instance, with at least "id" key with primary key value.

## Module contents

### `get_datastore(driver_name, dsn)`

### `DatastoreException`

### `DuplicateKeyException`

## datastore interface

### `datastore.query(collection, *filter, **params)`

Performs a query over collection of specified name. Optional positional arguments should be a 3-tuples consisting of: field name, operator, desired value. For example `("name", "=", "foo")` or `("id", ">", 4)`. All filter arguments are joined using AND logic. There are following keyword arguments currently supported:

* `offset`
* `limit`
* `sort`
* `dir`
* `single`

Following operators are supported:

* `=`
* `!=`
* `>`
* `<`
* `>=`
* `<=`
* `in` - value in set
* `nin` - value not in set
* `~` - regex match

### `datastore.get_one(collection, *filter, *params)`

Same as `query` with keyword argument `single` set to `True`.

### `datastore.get_by_id(collection, pkey)`

Returns single object by its primary key or `None`.

### `datastore.insert(collection, obj, pkey=None)`

### `datastore.update(collection, pkey, obj, upsert=False)`

### `datastore.delete(collection, pkey)`

## ConfigStore

A convenience class for accessing key-value store used for various global configuration settings.

### `configstore.get(key)`

### `configstore.set(key, value)`

### `configstore.list_children(root=None)`

## Examples