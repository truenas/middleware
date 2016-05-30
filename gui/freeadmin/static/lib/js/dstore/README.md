dstore
======

The dstore package is a data infrastructure framework, providing the tools for modelling and interacting with data collections and objects. dstore is designed to work with a variety of data storage mediums, and provide a consistent interface for accessing data across different user interface components. There are several key entities within dstore:

* [Collection](./docs/Collection.md) - This is a list of objects, which can be iterated over, sorted, filtered, and monitored for changes.
* [Store](./docs/Store.md) - A Store is a Collection that may also include the ability to identify, to add, remove, and update objects.

# [Included Stores](./docs/Stores.md)

The dstore package includes several store implementations that can be used for the needs of different applications. These include:

* `Memory` - This is a simple memory-based store that takes an array and provides access to the objects in the array through the store interface.
* `Request` - This is a simple server-based collection that sends HTTP requests following REST conventions to access and modify data requested through the store interface.
* `Rest` - This is a store built on `Request` that implements add, remove, and update operations using HTTP requests following REST conventions
* `RequestMemory` - This is a Memory based store that will retrieve its contents from a server/URL.
* `LocalDB` - This a store based on the browser's local database/storage capabilities. Data stored in this store will be persisted in the local browser.
* `Cache` - This is a store mixin that combines a master and caching store to provide caching functionality.
* `Tree` - This is a store mixin that provides hierarchical querying functionality, defining parent/child relationships for the display of data in a tree.
* `Trackable` - This a store mixin that adds index information to `add`, `update`, and `delete` events of tracked store instances. This adds a track() method for tracking stores.
* `SimpleQuery` - This is a mixin with basic querying functionality, which is extended by the Memory store, and can be used to add client side querying functionality to the Request/Rest store.

See the [Stores section](./docs/Stores.md) for more information these stores.

## [Collections](./docs/Collection.md)

A Collection is the interface for a collection of items, which can be filtered and sorted to create new collections. When implementing this interface, every method and property is optional, and is only needed if the functionality it provides is required, however all the included stores implement every method. A collection's list of objects may not be immediately retrieved from the underlying data storage until the it is accessed through `forEach()`, `fetch()`, or `fetchRange()`.

For more details on the Collection API and how to query, see the [Collection section](./docs/Collection.md)

## [Store](./docs/Store.md)

A store is an extension of a collection and is an entity that not only contains a set of objects, but also provides an interface for identifying, adding, modifying, removing, and querying data. See the [Store section](./docs/Store.md) for the details on the Store interface.

## Promise-based API and Synchronous Operations

All CRUD methods, such as `get`, `put`, `remove`, and `fetch`, return promises. However, stores and collections may provide synchronous versions of those methods with a "Sync" suffix (e.g., `Memory#fetchSync` to fetch synchronously from a `Memory` store).

# [Data Modelling](https://github.com/SitePen/dmodel)

In addition to handling collections of items, dstore works with the dmodel package to provides robust data modeling capabilities for managing individual objects. dmodel provides a data model class that includes multiple methods on data objects, for saving, validating, and monitoring objects for changes. By setting a model on stores, all objects returned from a store, whether a single object returned from a `get()` or an array of objects returned from a `fetch()`, will be an instance of the store's data model.

For more information, please see the [dmodel project](https://github.com/SitePen/dmodel).

# [Adapters](./docs/Adapters.md)

Adapters make it possible work with legacy Dojo object stores and widgets that expect Dojo object stores. dstore also includes an adapter for using a store with charts. See the [Adapters section](./docs/Adapters.md) for more information.

# [Testing](./docs/Testing.md)

dstore uses [Intern](http://theintern.io/) as its test runner. A full description
of how to setup testing is [available here](./docs/Testing.md). Tests can
either be run using the browser, or using [Sauce Labs](https://saucelabs.com/).
More information on writing your own tests with Intern can be found in the
[Intern wiki](https://github.com/theintern/intern/wiki).

# Dependencies

dstore's only required dependency is Dojo version 1.8 or higher. Running the unit tests requires the [intern-geezer](https://github.com/theintern/intern/tree/geezer) package (see the testing docs for [more information](./docs/Testing.md)). The extensions/RqlQuery module can leverage the [rql](https://github.com/persvr/rql) package, but the rql package is only needed if you use this extension.

# Contributing 

We welcome contributions, but please read the [contributing documentation](./docs/CONTRIBUTING.md) to help us be able to effectively receive your contributions and pull requests.

# License

The dstore project is available under the same dual BSD/AFLv2 license as the Dojo Toolkit.