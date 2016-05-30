# Store

A store is an extension of a [collection](./Collection.md) and is an entity that not only contains a set of objects, but also provides an interface for identifying, adding, modifying, removing, and querying data. Below is the definition of the store interface. Every method and property is optional, and is only needed if the functionality it provides is required (although the provided full stores (`Rest` and `Memory`) implement all the methods except `transaction()` and `getChildren()`). Every method returns a promise for the specified return value, unless otherwise noted.

In addition to the methods and properties inherited from [Collections](./Collection.md), the `Store` API also exposes the following properties and methods.

### Property Summary

Property | Description
-------- | -----------
`idProperty` | If the store has a single primary key, this indicates the property to use as the identity property. The values of this property should be unique. This defaults to "id".
`Model` | This is the model class to use for all the data objects that originate from this store. By default this will be set to null, so that all objects will be plain objects, but this property can be set to the class from `dmodel/Model` or any other model constructor. You can create your own model classes (and schemas), and assign them to a store. All objects that come from the store will have their prototype set such that they will be instances of the model. The default value of `null` will disable any prototype modifications and leave data as plain objects.
`defaultNewToStart` | If a new object is added to a store, this will indicate it if it should go to the start or end. By default, it will be placed at the end.

### Method Summary

Method | Description
------ | -------------
`get(id)` | This retrieves an object by its identity. This returns a promise for the object. If no object was found, the resolved value should be `undefined`.
`getIdentity(object)` | This returns an object's identity (note, this should always execute synchronously).
`put(object, [directives])` | This stores an object. It can be used to update or create an object. This returns a promise that may resolve to the object after it has been saved.
`add(object, [directives])` | This creates an object, and throws an error if the object already exists. This should return a promise for the newly created object.
`remove(id)` | This deletes an object, using the identity to indicate which object to delete. This returns a promise that resolves to a boolean value indicating whether the object was succcessfully removed.
`transaction()` | Starts a transaction and returns a transaction object. The transaction object should include a `commit()` and `abort()` to commit and abort transactions, respectively. Note, that a store user might not call `transaction()` prior to using put, delete, etc. in which case these operations effectively could be thought of as “auto-commit” style actions.
`create(properties)` | Creates and returns a new instance of the data model. The returned object will not be stored in the object store until it its save() method is called, or the store's add() is called with this object. This should always execute synchronously.
`getChildren(parent)` | This retrieves the children of the provided parent object. This should return a new collection representing the children.
`mayHaveChildren(parent)` | This should return true or false indicating whether or not a parent might have children. This should always return synchronously, as a way of checking if children might exist before actually retrieving all the children.
`getRootCollection()` | This should return a collection of the top level objects in a hierarchical store.
`emit(type, event)` | This can be used to dispatch event notifications, indicating changes to the objects in the collection. This should be called by `put`, `add`, and `remove` methods if the `autoEmit` property is `false`. This can also be used to notify stores if objects have changed from other sources (if a change has occurred on the server, from another user). There is a corresponding `on` method on [collections](./Collection.md#ontype-listener) for listening to data change events. Also, the [Trackable](./Stores.md#trackable) can be used to add index/position information to the events.

Stores that can perform synchronous operations may provide analogous methods for `get`, `put`, `add`, and `remove` that end with `Sync` to provide synchronous support. For example `getSync(id)` will directly return an object instead of a promise. The `dstore/Memory` store provides `Sync` methods.