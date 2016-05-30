# Collection

A Collection is the interface for a collection of items, which can be filtered or sorted to create new collections. When implementing this interface, every method and property is optional, and is only needed if the functionality it provides is required. However, all the included collections implement every method. Note that the objects in the collection might not be immediately retrieved from the underlying data storage until they are actually accessed through `forEach()`, `fetch()`, or `fetchRange()`. These fetch methods return a snapshot of the data, and if the data has changed, these methods can later be used to retrieve the latest data.

## Querying

Several methods are available for querying collections. These methods allow you to define a query through several steps. Normally, stores are queried first by calling `filter()` to specify which objects to be included, if the filtering is needed. Next, if an order needs to be specified, the `sort()` method is called to ensure the results will be sorted. A typical query from a store would look like:

    store.filter({priority: 'high'}).sort('dueDate').forEach(function (object) {
            // called for each item in the final result set
        });

In addition, the `track()` method may be used to track store changes, ensuring notifications include index information about object changes, and keeping result sets up-to-date after a query. The `fetch()` method is an alternate way to retrieve results, providing a promise to an array for accessing query results. The sections below describes each of these methods and how to use them.

## Filtering

Filtering is used to specify a subset of objects to be returned in a filtered collection. The simplest use of the `filter()` method is to call it with a plain object as the argument, that specifies name-value pairs that the returned objects must match. Or a filter builder can be used to construct more sophisticated filter conditions. To use the filter builder, first construct a new filter object from the `Filter` constructor on the collection you would be querying:

	var filter = new store.Filter();

We now have a `filter` object, that represents a filter, without any operators applied yet. We can create new filter objects by calling the operator methods on the filter object. The operator methods will return new filter objects that hold the operator condition. For example, to specify that we want to retrieve objects with a `priority` property with a value of `"high"`, and `stars` property with a value greater than `5`, we could write:

	var highPriorityFiveStarFilter = filter.eq('priority', 'high').gt('stars', 5);

This filter object can then be passed as the argument to the `filter()` method on a collection/store:

	var highPriorityFiveStarCollection = store.filter(highPriorityFiveStarFilter);

The following methods are available on the filter objects. First are the property filtering methods, which each take a property name as the first argument, and a property value to compare for the second argument:
* `eq`: Property values must equal the filter value argument.
* `ne`: Property values must not equal the filter value argument.
* `lt`: Property values must be less than the filter value argument.
* `lte`: Property values must be less than or equal to the filter value argument.
* `gt`: Property values must be greater than the filter value argument.
* `gte`: Property values must be greater than or equal to the filter value argument.
* `in`: An array should be passed in as the second argument, and property values must be equal to one of the values in the array.
* `match`: Property values must match the provided regular expression.
* `contains`: Filters for objects where the specified property's value is an array and the array contains any value that equals the provided value or satisfies the provided expression.

The following are combinatorial methods:
* `and`: This takes two arguments that are other filter objects, that both must be true.
* `or`: This takes two arguments that are other filter objects, where one of the two must be true.

### Nesting

A few of the filters can also be built upon with other collections (potentially from other stores). In particular, you can provide a collection as the argument for the `in` or `contains` filter. This provides functionality similar to nested queries or joins. This generally will need to be combined with a `select` to return the correct values for matching. For example, if we wanted to find all the tasks in high priority projects, where the `task` store has a `projectId` property/column that is a foreign key, referencing objects in a `project` store. We can perform our nested query:

	var tasksOfHighPriorityProjects = taskStore.filter(
			new Filter().in('projectId',
				projectStore.filter({priority: 'high'}).select('id')));

### Implementations

Different stores may implement filtering in different ways. The `dstore/Memory` will perform filtering in memory. The `dstore/Request`/`dstore/Rest` stores will translate the filters into URL query strings to send to the server. Simple queries will be in standard URL-encoded query format and complex queries will conform to [RQL](https://github.com/persvr/rql) syntax (which is a superset of standard query format).

New filter methods can be created by subclassing `dstore/Filter` and adding new methods. New methods can be created by calling `Filter.filterCreator` and by providing the name of the new method. If you will be using new methods with stores that mix in `SimpleQuery` like memory stores, you can also add filter comparators by overriding the `_getFilterComparator` method, returning comparators for the additional types, and delegating to `this.inherited` for the rest.

For the `dstore/Request`/`dstore/Rest` stores, you can define alternate serializations of filters to URL queries for existing or new methods by overriding the `_renderFilterParams`. This method is called with a filter object (and by default is recursively called by combinatorial operators), and should return a string serialization of the filter, that will be inserted into the query string of the URL sent to the server.

The filter objects themselves consist of tree structures. Each filter object has two properties, the operator `type`, which corresponds to whichever operator was used (like `eq` or `and`), and the `args`, which  is an array of values provided to the operator. With `and` and `or` operators, the arguments are other filter objects, forming a hierarchy. When filter operators are chained together (through sequential calls), they are combined with the `and` operator (each operator defined in a sub-filter object).

## Collection API

The following property and methods are available on dstore collections:

### Property Summary

Property | Description
-------- | -----------
`Model` | This constructor represents the data model class to use for the objects returned from the store. All objects returned from the store should have their prototype set to the prototype property of the model, such that objects from this store should return true from `object instanceof collection.Model`.

### Method Summary

#### `filter(query)`

This filters the collection, returning a new subset collection. The query can be an object, or a filter object, with the properties defining the constraints on matching objects. Some stores, like server or RQL stores, may accept string-based queries. Stores with in-memory capabilities (like `dstore/Memory`) may accept a function for filtering as well, but using the filter builder will ensure the greatest cross-store compatibility.

#### `sort(property, [descending])`

This sorts the collection, returning a new ordered collection. Note that if sort is called multiple times, previous sort calls may be ignored by the store (it is up to store implementation how to handle that). If a multiple sort order is desired, use the array of sort orders defined by below.

#### `sort([highestSortOrder, nextSortOrder...])`

This also sorts the collection, but can be called to define multiple sort orders by priority. Each argument is an object with a `property` property and an optional `descending` property (defaults to ascending, if not set), to define the order. For example: `collection.sort([{property:'lastName'}, {property: 'firstName'}])` would result in a new collection sorted by lastName, with firstName used to sort identical lastName values.

#### select([property, ...])

This selects specific properties that should be included in the returned objects.

#### select(property)

This will indicate that the return results will consist of the values of the given property of the queried objects. For example, this would return a collection of name values, pulled from the original collection of objects:

	collection.select('name');

#### `forEach(callback, thisObject)`

This iterates over the query results.  Note that this may be executed asynchronously and the callback may be called after this function returns. This will return a promise to indicate the completion of the iteration. This method forces a fetch of the data.

#### `fetch()`

Normally collections may defer the execution (like making an HTTP request) required to retrieve the results until they are actually accessed. Calling `fetch()` will force the data to be retrieved, returning a promise to an array.

#### `fetchRange({start: start, end: end})`

This fetches a range of objects from the collection, returning a promise to an array. The returned (and resolved) promise should have a `totalLength`
property with a promise that resolves to a number indicating the total number of objects available in the collection.

#### `on(type, listener)`

This allows you to define a listener for events that take place on the collection or parent store. When an event takes place, the listener will be called with an event object as the single argument. The following event types are defined:

Type | Description
-------- | -----------
`add` | This indicates that a new object was added to the store. The new object is available on the `target` property.
`update` | This indicates that an object in the stores was updated. The updated object is available on the `target` property.
`delete` | This indicates that an object in the stores was removed. The id of the object is available on the `id` property.

There is also a corresponding `emit(type, event)` method (from the [Store interface](Store.md#method-summary)) that can be used to emit events when objects have changed.

#### `track()`

This method will create a new collection that will be tracked and updated as the parent collection changes. This will cause the events sent through the resulting collection to include an `index` and `previousIndex` property to indicate the position of the change in the collection. This is an optional method, and is usually provided by `dstore/Trackable`. For example, you can create an observable store class, by using `dstore/Trackable` as a mixin:

	var TrackableMemory = declare([Memory, Trackable]);

Trackable requires client side querying functionality. Client side querying functionality is available in `dstore/SimpleQuery` (and inherited by `dstore/Memory`). If you are using a `Request`, `Rest`, or other server side store, you will need to implement client-side query functionality (by implemented querier methods), or mixin `SimpleQuery`:

	var TrackableRest = declare([Rest, SimpleQuery, Trackable]);

Once we have created a new instance from this store, we can track a collection, which could be the top level store itself, or a downstream filtered or sorted collection:

	var store = new TrackableMemory({data: ...});
	var filteredSorted = store.filter({inStock: true}).sort('price');
	var tracked = filteredSorted.track();

Once we have a tracked collection, we can listen for notifications:

	tracked.on('add, update, delete', function(event){
		var newIndex = event.index;
		var oldIndex = event.previousIndex;
		var object = event.target;
	});

Trackable requires fetched data to determine the position of modified objects and can work with either full or partial data. We can do a `fetch()` or `forEach()` to access all the items in the filtered collection:

	tracked.fetch();

Or we can do a `fetchRange()` to make individual range requests for items in the collection:

	tracked.fetchRange(0, 10);

Trackable will keep track of each page of data, and send out notifications based on the data it has available, along with index information, indicating the new and old position of the object that was modified. Regardless of whether full or partial data is fetched, tracked events and the indices they report are relative to the entire collection, not relative to individual fetched ranges. Tracked events also include a `totalLength` property indicating the total length of the collection.

If an object is added or updated, and falls outside of all of the fetched ranges, the index will be undefined. However, if the object falls between fetched ranges (but within one), there will also be a `beforeIndex` that indicates the index of the first object that the new or update objects comes before.

### Custom Querying

Custom query methods can be created using the `dstore/QueryMethod` module. We can define our own query method, by extending a store, and defining a method with the `QueryMethod`. The QueryMethod constructor should be passed an object with the following possible properties:
* `type` - This is a string, identifying the query method type.
* `normalizeArguments` - This can be a function that takes the arguments passed to the method, and normalizes them for later execution.
* `applyQuery` - This is an optional function that can be called on the resulting collection that is returned from the generated query method.
* `querierFactory` - This is an optional function that can be used to define the computation of the set of objects returned from a query, on client-side or in-memory stores. It is called with the normalized arguments, and then returns a new function that will be called with an array, and is expected to return a new array.

For example, we could create a `getChildren` method that queried for children object, by simply returning the children property array from a parent:

	declare([Memory], {
		getChildren: new QueryMethod({
			type: 'children',
			querierFactory: function (parent) {
				var parentId = this.getIdentity(parent);

				return function (data) {
					// note: in this case, the input data is ignored as this querier
					// returns an object's array of children instead

					// return the children of the parent
					// or an empty array if the parent no longer exists
					var parent = this.getSync(parentId);
					return parent ? parent.children : [];
				};
			}
		})
