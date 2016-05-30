# Adapters

## StoreAdapter

The `dstore/legacy/StoreAdapter` module allows a Dojo object store to be used as a dstore store. Create an adapted version of an existing `dstore` object store by calling `new StoreAdapter({objectStore: objectStore})`.
```js
require([
    'dstore/legacy/StoreAdapter',
    'dojo/store/Memory'
], function(StoreAdapter) {
    var objectStore = new Memory({...});
    var adaptedStore = new StoreAdapter({objectStore: objectStore});
});
``` 

This provides all the methods and properties inherited from `dstore/api/Store`.

## DstoreAdapter

The `dstore/legacy/DstoreAdapter` module allows a dstore store to be used as a legacy Dojo object store. Create an adapted version of an existing dstore store by creating a `DstoreAdapter` instance with the `store` property referencing the dstore:
```js
require([
    'dstore/legacy/DstoreAdapter',
    'dstore/Memory'
], function(DstoreAdapter, Memory) {
    var store = new Memory({...});
    var adaptedStore = new DstoreAdapter(store);
});
```
If the dstore store is trackable (mixed in `dstore/Trackable`), the result sets returned from `query()` calls will be observable (have an `observe()` method).

## StoreSeries

The `dstore/charting/StoreSeries` module allows a dstore object to be used as a `Series` in a Dojox chart.
```js
require([
    'dstore/charting/StoreSeries'
], function (StoreSeries) {
    //... create a store and a chart ...
    // Adds a StoreSeries to the y axis.
    chart.addSeries('y', new StoreSeries(store));
});
```

### Constructor

The `StoreSeries` constructor expects 2 parameters.

Property | Description
-------- | -----------
`store` | A dstore object store.
`value` | An optional string, object or function that describes which property or properties to extract from each store item to include in the series.  If this parameter is omitted, then "value" is used by default.

### Method Summary

Method | Description
------ | -------------
`setSeriesObject(series)` | Sets the `dojox\charting\Series` object that will render the data.
`fetch()` | Retrieves all of the data from the store.  This method is initially called when the adapter is constructed.  If the store is observable, the adapter will register an observer to listen for updates from the store.
`destroy()` | Causes the adapter to release all resources.
