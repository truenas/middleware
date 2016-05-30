# Included Stores

The dstore package includes several store implementations that can be used for the needs of different applications. These include:

* `Memory` - This is a simple memory-based store that takes an array and provides access to the objects in the array through the store interface.
* `Request` - This is a simple server-based collection that sends HTTP requests following REST conventions to access and modify data requested through the store interface.
* `Rest` - This is a store built on `Request` that implements add, remove, and update operations using HTTP requests following REST conventions.
* `RequestMemory` - This is a Memory based store that will retrieve its contents from a server/URL.
* `LocalDB` - This a store based on the browser's local database/storage capabilities. Data stored in this store will be persisted in the local browser.
* `Cache` - This is a store mixin that combines a master and caching store to provide caching functionality.
* `Trackable` - This a store mixin that adds index information to `add`, `update`, and `remove` events of tracked store instances. This adds a track() method for tracking stores.
* `Tree` - This is a store mixin that provides hierarchical querying functionality, defining a parent/child relationships for the display of data in a tree.
* `SimpleQuery` - This is a mixin with basic querying functionality, which is extended by the Memory store, and can be used to add client side querying functionality to the Request/Rest store.
* `Store` - This is a base store, with the base methods that are used by all other stores.

## Constructing Stores

All the stores can be instantiated with an options argument to the constructor, to provide properties to be copied to the store. This can include methods to be added to the new store.

Stores can also be constructed by combining a base store with mixins. The various store mixins are designed to be combined through dojo `declare` to create a class to instantiate a store. For example, if you wish to add tracking and tree functionality to a Memory store, we could combine these:

    // create the class based on the Memory store with added functionality
    var TrackedTreeMemoryStore = declare([Memory, Trackable, Tree]);
    // now create an instance
    var myStore = new TrackedTreeMemoryStore({data: [...]});

The store mixins can only be used as mixins, but stores can be combined with other stores as well. For example, if we wanted to add the Rest functionality to the RequestMemory store (so the entire store data was retrieved from the server on construction, but data changes are sent to the server), we could write:

    var RestMemoryStore = declare([Rest, RequestMemory]);
    // now create an instance
    var myStore = new RestMemoryStore({target: '/data-source/'});

Another common case is needing to add tracking to the `dstore/Rest` store, which requires client side querying, which be provided by `dstore/SimpleQuery`:

var TrackedRestStore = declare([Rest, SimpleQuery, Trackable]);

## Memory

The Memory store is a basic client-side in-memory store that can be created from a simple JavaScript array. When creating a memory store, the data (which should be an array of objects) can be provided in the `data` property to the constructor. The data should be an array of objects, and all the objects are considered to be existing objects and must have identities (this is not "creating" new objects, no events are fired for the objects that are provided, nor are identities assigned).

For example:

    myStore = new Memory({
        data: [{
            id: 1,
            aProperty: ...,
            ...
        }]
    });

The `Memory` store provides synchronous equivalents of standard asynchronous store methods, including `getSync(id)`, `addSync(object, options)`, `putSync(object, options)`, and `removeSync(id)`. These methods directly return objects or results, without a promise.

## Request

This is a simple collection for accessing data by retrieval from a server (typically through XHR). The target URL path to use for requests can be defined with the `target` property. A request for data will be sent to the server when a fetch occurs (due a call to `fetch()`, `fetchRange()`, or `forEach()`). Request supports several properties for defining the generation of query strings:
* `sortParam` - This will specify the query parameter to use for specifying the sort order. This will default to `sort(<properties>)` in the query string.
* `selectParam` - This will specify the query parameter to use for specifying the `select` properties. This will default to `select(<properties>)` in the query string.
* `rangeStartParam` and `rangeCountParam` - This will specify the query parameter to use for specifying the range. This will default to `limit(<count>,<start>)` in the query string.
* `useRangeHeaders` - This will specify that range information should be specified in the `Range` header.

## Rest

This store extends the Request store, to add functionality for adding, updating, and removing objects. All modifications trigger HTTP requests to the server using the corresponding RESTful HTTP methods. A `get()` triggers a `GET`, `remove()` triggers a `DELETE`, and `add()` and `put()` will trigger a `PUT` if an id is available or provided, and a `POST` will be used to create new objects with server provided ids.

For example:

    myStore = new Rest({
        target: '/PathToData/'
    });

All modification or retrieval methods (except `getIdentity()`) on `Request` and `Rest` execute asynchronously, returning a promise.

## Store

This is the base class used for all stores, providing basic functionality for tracking collection states and converting objects to be model instances. This (or any of the other classes above) can be extended for creating custom stores.

## RequestMemory

This store provides client-side querying functionality, but will load its data from the server, using the provided URL. This is
an asynchronous store since queries and data retrieval may be made before the data has been retrieved from the server.

## LocalDB

This a store based on the browser's local database/storage capabilities. Data stored in this store will be persisted in the local browser. The LocalDB will automatically load the best storage implementation based on browser's capabilities. These storage implementation follow the same interface. `LocalDB` will attempt to load one of these stores (highest priority first, and these can also be used directly if you do not want automatic selection):

* `dstore/db/IndexedDB` - This uses the IndexedDB API. This is available on the latest version of all major browsers (introduced in IE 10 and Safari 7.1/8, but with some serious bugs).
* `dstore/db/SQL` - This uses the WebSQL API. This is available on Safari and Chrome.
* `dstore/db/LocalStorage` - This uses the localStorage API. This is available on all major browsers, going back to IE8. The localStorage API does not provide any indexed querying, so this loads the entire database in memory. This can be very expensive for large datasets, so this store is generally avoided, except to provide functionality on old versions of IE.
* `dstore/db/has` - This is not a store, but provides feature `has` tests for `indexeddb` and `sql`.

The `LocalDB` stores requires a few extra parameters, not needed by other stores. First, it needs a database configuration object. A database configuration object defines all the stores or tables that are used by the stores, and which properties to index. There should be a single database configuration object for the entire application, and it should be passed to all the store instances. The configuration object should include a version (which should be incremented whenever the configuration is changed), and a set of stores in the `stores` object. Within the stores object, each property that will be used should be defined. Each property value should have a property configuration object with the following optional properties:

* `preference` - This defines the priority of using this property for index-based querying. This should be a larger number for more unique properties. A boolean property would generally have a `preference` of 1, and a completely unique property should be 100.
* `indexed` - This is a boolean indicating if a property should be indexed. This defaults to true.
* `multiEntry` - This indicates the property will have an array of values, and should be indexed correspondingly. Internet Explorer's implementation of IndexedDB does not currently support `multiEntry`.
* `autoIncrement` - This indicates if a property should automatically increment.

Alternately a number can be provided as a property configuration, and will be used as the `preference`.

An example database configuration object is:

    var dbConfig = {
        version: 5,
        stores: {
            posts: {
                name: 10,
                id: {
                    autoIncrement: true,
                    preference: 100
                },
                tags: {
                    multiEntry: true,
                    preference: 5
                },
                content: {
                    indexed: false
                }
            },
            commments: {
                author: {},
                content: {
                    indexed: false
                }
            }
        }
    };

In addition, each store should define a `storeName` property to identify which database store corresponds to the store instance. For example:

    var postsStore = new LocalDB({dbConfig: dbConfig, storeName: 'posts'});
    var commentsStore = new LocalDB({dbConfig: dbConfig, storeName: 'comments'});

Once created, these stores can be used like any other store.

## Cache

This is a mixin that can be used to add caching functionality to a store. This can also be used to wrap an existing store, by using the static `create` function:

    var cachedStore = Cache.create(existingStore, {
        cachingStore: new Memory()
    });

This store has the following properties and methods:

Name | Description
---- | -----------
`cachingStore` | This can be used to define the store to be used for caching the data. By default a Memory store will be used.
`isValidFetchCache` | This is a flag that indicates if the data fetched for a collection/store can be cached to fulfill subsequent fetches. This is false by default, and the value will be inherited by downstream collections. It is important to note that only full `fetch()` requests will fill the cache for subsequent `fetch()` requests. `fetchRange()` requests will not fulfill a collection, and subsequent `fetchRange()` requests will not go to the cache unless the collection has been fully loaded through a `fetch()` request.
`allLoaded` | This is a flag indicating that the given collection/store has its data loaded. This can be useful if you want to provide a caching store prepopulated with data for a given collection. If you are setting this to true, make sure you set `isValidFetchCache` to true as well to indicate that the data is available for fetching.
`canCacheQuery(method, args)' | This can be a boolean or a method that will indicate if a collection can be cached (if it should have `isValidFetchCache` set to true), based on the query method and arguments used to derive the collection.
`isLoaded(object)` | This can be defined to indicate if a given object in a query can be cached (by default, objects are cached).



## Tree

This is a mixin that provides basic support for hierarchical data. This implements several methods that can then be used by hierarchical UI components (like [dgrid](https://github.com/SitePen/dgrid) with a tree column). This mixin uses a parent-based approach to finding children, retrieving the children of an object by querying for objects that have `parent` property with the id of the parent object. In addition, objects may have a `hasChildren` property to indicate if they have children (if the property is absent, it is assumed that they may have children). This mixin implements the following methods:

* `getChildren(parent)` - This returns a collection representing the children of the provided parent object. This is produced by filtering for objects that have a `parent` property with the id of the parent object.
* `mayHaveChildren(parent)` - This synchronously returns a boolean indicating whether or not the parent object might have children (the actual children may need to be retrieved asynchronously).
* `getRootCollection()` - This returns the root collection, the collection of objects with `parent` property that is `null`.

The Tree mixin may serve as an example for alternate hierarchical implementations. By implementing these methods as they are in `dstore/Tree`, one could change the property names for data that uses different parent references or indications of children. Another option would be define the children of an object as direct references from the parent object. In this case, you would define `getChildren` to associate the `parent` object with the returned collection and override `fetch` and `fetchRange` to return a promise to the array of the children of the parent.

## Trackable

The Trackable mixin adds functionality for tracking the index positions of objects as they are added, updated, or deleted. The `Trackable` mixin adds a `track()` method to create a new tracked collection. When events are fired (from modification operations, or other sources), the tracked can match the changes from the events to any cached data in the collection (which may be ordered by sorting, or filtered), and decorates the events with index positions. More information about tracked collections and events can be found in the collections [documentation](Collection.md#track).

## Resource Query Language

[Resource Query Language (RQL)](https://github.com/persvr/rql) is a query language specifically designed to be easily embedded in URLs (it is a compatible superset of standard encoded query parameters), as well as easily interpreted within JavaScript for client-side querying. Therefore RQL is a query language suitable for consistent client and server-delegated queries. The dstore packages serializes complex filter/queries into RQL (RQL supersets standard query parameters, and so simple queries are simply serialized as standard query parameters).

dstore also includes support for using RQL as the query language for filtering. This can be enabled by mixin `dstore/extensions/RqlQuery` into your collection type:

    require([
        'dojo/_base/declare',
        'dstore/Memory',
        'dstore/extensions/RqlQuery'
    ], function (declare, Memory, RqlQuery) {
        var RqlStore = declare([ Memory, RqlQuery ]);
        var rqlStore = new RqlStore({
            ...
        });

        rqlStore.filter('price<10|rating>3').forEach(function (product) {
            // return each product that has a price less than 10 or a rating greater than 3
        });
    }};

Make sure you have installed/included the [rql](https://github.com/persvr/rql) package if you are using the RQL query engine.
