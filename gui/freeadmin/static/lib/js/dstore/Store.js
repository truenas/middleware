define([
	'dojo/_base/lang',
	'dojo/_base/array',
	'dojo/aspect',
	'dojo/has',
	'dojo/when',
	'dojo/Deferred',
	'dojo/_base/declare',
	'./QueryMethod',
	'./Filter',
	'dojo/Evented'
], function (lang, arrayUtil, aspect, has, when, Deferred, declare, QueryMethod, Filter, Evented) {

	// module:
	//		dstore/Store
	/* jshint proto: true */
	// detect __proto__, and avoid using it on Firefox, as they warn about
	// deoptimizations. The watch method is a clear indicator of the Firefox
	// JS engine.
	has.add('object-proto', !!{}.__proto__ && !({}).watch);
	var hasProto = has('object-proto');

	function emitUpdateEvent(type) {
		return function (result, args) {
			var self = this;
			when(result, function (result) {
				var event = { target: result },
					options = args[1] || {};
				if ('beforeId' in options) {
					event.beforeId = options.beforeId;
				}
				self.emit(type, event);
			});

			return result;
		};
	}

	var base = Evented;
	/*=====
	base = [ Evented, Collection ];
	=====*/

	return /*==== Store= ====*/declare(base, {
		constructor: function (options) {
			// perform the mixin
			options && declare.safeMixin(this, options);

			if (this.Model && this.Model.createSubclass) {
				// we need a distinct model for each store, so we can
				// save the reference back to this store on it.
				// we always create a new model to be safe.
				this.Model = this.Model.createSubclass([]).extend({
					// give a reference back to the store for saving, etc.
					_store: this
				});
			}

			// the object the store can use for holding any local data or events
			this.storage = new Evented();
			var store = this;
			if (this.autoEmitEvents) {
				// emit events when modification operations are called
				aspect.after(this, 'add', emitUpdateEvent('add'));
				aspect.after(this, 'put', emitUpdateEvent('update'));
				aspect.after(this, 'remove', function (result, args) {
					when(result, function () {
						store.emit('delete', {id: args[0]});
					});
					return result;
				});
			}
		},

		// autoEmitEvents: Boolean
		//		Indicates if the events should automatically be fired for put, add, remove
		//		method calls. Stores may wish to explicitly fire events, to control when
		//		and which event is fired.
		autoEmitEvents: true,

		// idProperty: String
		//		Indicates the property to use as the identity property. The values of this
		//		property should be unique.
		idProperty: 'id',

		// queryAccessors: Boolean
		//		Indicates if client-side query engine filtering should (if the store property is true)
		//		access object properties through the get() function (enabling querying by
		//		computed properties), or if it should (by setting this to false) use direct/raw
		// 		property access (which may more closely follow database querying style).
		queryAccessors: true,

		getIdentity: function (object) {
			// summary:
			//		Returns an object's identity
			// object: Object
			//		The object to get the identity from
			// returns: String|Number

			return object.get ? object.get(this.idProperty) : object[this.idProperty];
		},

		_setIdentity: function (object, identityArg) {
			// summary:
			//		Sets an object's identity
			// description:
			//		This method sets an object's identity and is useful to override to support
			//		multi-key identities and object's whose properties are not stored directly on the object.
			// object: Object
			//		The target object
			// identityArg:
			//		The argument used to set the identity

			if (object.set) {
				object.set(this.idProperty, identityArg);
			} else {
				object[this.idProperty] = identityArg;
			}
		},

		forEach: function (callback, thisObject) {
			var collection = this;
			return when(this.fetch(), function (data) {
				for (var i = 0, item; (item = data[i]) !== undefined; i++) {
					callback.call(thisObject, item, i, collection);
				}
				return data;
			});
		},
		on: function (type, listener) {
			return this.storage.on(type, listener);
		},
		emit: function (type, event) {
			event = event || {};
			event.type = type;
			try {
				return this.storage.emit(type, event);
			} finally {
				// Return the initial value of event.cancelable because a listener error makes it impossible
				// to know whether the event was actually canceled
				return event.cancelable;
			}
		},

		// parse: Function
		//		One can provide a parsing function that will permit the parsing of the data. By
		//		default we assume the provide data is a simple JavaScript array that requires
		//		no parsing (subclass stores may provide their own default parse function)
		parse: null,

		// stringify: Function
		//		For stores that serialize data (to send to a server, for example) the stringify
		//		function can be specified to control how objects are serialized to strings
		stringify: null,

		// Model: Function
		//		This should be a entity (like a class/constructor) with a 'prototype' property that will be
		//		used as the prototype for all objects returned from this store. One can set
		//		this to the Model from dmodel/Model to return Model objects, or leave this
		//		to null if you don't want any methods to decorate the returned
		//		objects (this can improve performance by avoiding prototype setting),
		Model: null,

		_restore: function (object, mutateAllowed) {
			// summary:
			//		Restores a plain raw object, making an instance of the store's model.
			//		This is called when an object had been persisted into the underlying
			//		medium, and is now being restored. Typically restored objects will come
			//		through a phase of deserialization (through JSON.parse, DB retrieval, etc.)
			//		in which their __proto__ will be set to Object.prototype. To provide
			//		data model support, the returned object needs to be an instance of the model.
			//		This can be accomplished by setting __proto__ to the model's prototype
			//		or by creating a new instance of the model, and copying the properties to it.
			//		Also, model's can provide their own restore method that will allow for
			//		custom model-defined behavior. However, one should be aware that copying
			//		properties is a slower operation than prototype assignment.
			//		The restore process is designed to be distinct from the create process
			//		so their is a clear delineation between new objects and restored objects.
			// object: Object
			//		The raw object with the properties that need to be defined on the new
			//		model instance
			// mutateAllowed: boolean
			//		This indicates if restore is allowed to mutate the original object
			//		(by setting its __proto__). If this isn't true, than the restore should
			//		copy the object to a new object with the correct type.
			// returns: Object
			//		An instance of the store model, with all the properties that were defined
			//		on object. This may or may not be the same object that was passed in.
			var Model = this.Model;
			if (Model && object) {
				var prototype = Model.prototype;
				var restore = prototype._restore;
				if (restore) {
					// the prototype provides its own restore method
					object = restore.call(object, Model, mutateAllowed);
				} else if (hasProto && mutateAllowed) {
					// the fast easy way
					// http://jsperf.com/setting-the-prototype
					object.__proto__ = prototype;
				} else {
					// create a new object with the correct prototype
					object = lang.delegate(prototype, object);
				}
			}
			return object;
		},

		create: function (properties) {
			// summary:
			//		This creates a new instance from the store's model.
			//	properties:
			//		The properties that are passed to the model constructor to
			//		be copied onto the new instance. Note, that should only be called
			//		when new objects are being created, not when existing objects
			//		are being restored from storage.
			return new this.Model(properties);
		},

		_createSubCollection: function (kwArgs) {
			var newCollection = lang.delegate(this.constructor.prototype);

			for (var i in this) {
				if (this._includePropertyInSubCollection(i, newCollection)) {
					newCollection[i] = this[i];
				}
			}

			return declare.safeMixin(newCollection, kwArgs);
		},

		_includePropertyInSubCollection: function (name, subCollection) {
			return !(name in subCollection) || subCollection[name] !== this[name];
		},

		// queryLog: __QueryLogEntry[]
		//		The query operations represented by this collection
		queryLog: [],	// NOTE: It's ok to define this on the prototype because the array instance is never modified

		filter: new QueryMethod({
			type: 'filter',
			normalizeArguments: function (filter) {
				var Filter = this.Filter;
				if (filter instanceof Filter) {
					return [filter];
				}
				return [new Filter(filter)];
			}
		}),

		Filter: Filter,

		sort: new QueryMethod({
			type: 'sort',
			normalizeArguments: function (property, descending) {
				var sorted;
				if (typeof property === 'function') {
					sorted = [ property ];
				} else {
					if (property instanceof Array) {
						sorted = property.slice();
					} else if (typeof property === 'object') {
						sorted = [].slice.call(arguments);
					} else {
						sorted = [{ property: property, descending: descending }];
					}

					sorted = arrayUtil.map(sorted, function (sort) {
						// copy the sort object to avoid mutating the original arguments
						sort = lang.mixin({}, sort);
						sort.descending = !!sort.descending;
						return sort;
					});
					// wrap in array because sort objects are a single array argument
					sorted = [ sorted ];
				}
				return sorted;
			}
		}),

		select: new QueryMethod({
			type: 'select'
		}),

		_getQuerierFactory: function (type) {
			var uppercaseType = type[0].toUpperCase() + type.substr(1);
			return this['_create' + uppercaseType + 'Querier'];
		}

/*====,
		get: function (id) {
			// summary:
			//		Retrieves an object by its identity
			// id: Number
			//		The identity to use to lookup the object
			// returns: Object
			//		The object in the store that matches the given id.
		},
		put: function (object, directives) {
			// summary:
			//		Stores an object
			// object: Object
			//		The object to store.
			// directives: dstore/Store.PutDirectives?
			//		Additional directives for storing objects.
			// returns: Object
			//		The object that was stored, with any changes that were made by
			//		the storage system (like generated id)
		},
		add: function (object, directives) {
			// summary:
			//		Creates an object, throws an error if the object already exists
			// object: Object
			//		The object to store.
			// directives: dstore/Store.PutDirectives?
			//		Additional directives for creating objects.
			// returns: Object
			//		The object that was stored, with any changes that were made by
			//		the storage system (like generated id)
		},
		remove: function (id) {
			// summary:
			//		Deletes an object by its identity
			// id: Number
			//		The identity to use to delete the object
		},
		transaction: function () {
			// summary:
			//		Starts a new transaction.
			//		Note that a store user might not call transaction() prior to using put,
			//		delete, etc. in which case these operations effectively could be thought of
			//		as "auto-commit" style actions.
			// returns: dstore/Store.Transaction
			//		This represents the new current transaction.
		},
		getChildren: function (parent) {
			// summary:
			//		Retrieves the children of an object.
			// parent: Object
			//		The object to find the children of.
			// returns: dstore/Store.Collection
			//		A result set of the children of the parent object.
		}
====*/
	});
});


/*====
	var Collection = declare(null, {
		// summary:
		//		This is an abstract API for a collection of objects, which can be filtered,
		//		sorted, and sliced to create new collections. This is considered to be base
		//		interface for all stores and  query results in dstore. Note that the objects in the
		//		collection may not be immediately retrieved from the underlying data
		//		storage until they are actually accessed through forEach() or fetch().

		filter: function (query) {
			// summary:
			//		Filters the collection, returning a new subset collection
			// query: String|Object|Function
			//		The query to use for retrieving objects from the store.
			// returns: Collection
		},
		sort: function (property, descending) {
			// summary:
			//		Sorts the current collection into a new collection, reordering the objects by the provided sort order.
			// property: String|Function
			//		The property to sort on. Alternately a function can be provided to sort with
			// descending?: Boolean
			//		Indicate if the sort order should be descending (defaults to ascending)
			// returns: Collection
		},
		fetchRange: function (kwArgs) {
			// summary:
			//		Retrieves a range of objects from the collection, returning a promise to an array.
			// kwArgs.start: Number
			//		The starting index of objects to return (0-indexed)
			// kwArgs.end: Number
			//		The exclusive end of objects to return
			// returns: Collection
		},
		forEach: function (callback, thisObject) {
			// summary:
			//		Iterates over the query results, based on
			//		https://developer.mozilla.org/en/Core_JavaScript_1.5_Reference/Objects/Array/forEach.
			//		Note that this may executed asynchronously (in which case it will return a promise),
			//		and the callback may be called after this function returns.
			// callback:
			//		Function that is called for each object in the query results
			// thisObject:
			//		The object to use as |this| in the callback.
			// returns:
			//		undefined|Promise
		},
		fetch: function () {
			// summary:
			//		This can be called to materialize and request the data behind this collection.
			//		Often collections may be lazy, and won't retrieve their underlying data until
			//		forEach or fetch is called. This returns an array, or for asynchronous stores,
			//		this will return a promise, resolving to an array of objects, once the
			//		operation is complete.
			//	returns Array|Promise
		},
		on: function (type, listener) {
			// summary:
			//		This registers a callback for notification of when data is modified in the query results.
			// type: String
			//		There are four types of events defined in this API:
			//		- add - A new object was added
			//		- update - An object was updated
			//		- delete - An object was deleted
			// listener: Function
			//		The listener function is called when objects in the query results are modified
			//		to affect the query result. The listener function is called with a single event object argument:
			//		| listener(event);
			//
			//		- The event object as the following properties:
			//		- type - The event type (of the four above)
			//		- target - This indicates the object that was create or modified.
			//		- id - If an object was removed, this indicates the object that was removed.
			//		The next two properties will only be available if array tracking is employed,
			//		which is usually provided by dstore/Trackable
			//		- previousIndex - The previousIndex parameter indicates the index in the result array where
			//		the object used to be. If the value is -1, then the object is an addition to
			//		this result set (due to a new object being created, or changed such that it
			//		is a part of the result set).
			//		- index - The inex parameter indicates the index in the result array where
			//		the object should be now. If the value is -1, then the object is a removal
			//		from this result set (due to an object being deleted, or changed such that it
			//		is not a part of the result set).

		}
	});

	Collection.SortInformation = declare(null, {
		// summary:
		//		An object describing what property to sort on, and the direction of the sort.
		// property: String
		//		The name of the property to sort on.
		// descending: Boolean
		//		The direction of the sort.  Default is false.
	});
	Store.Collection = Collection;

	Store.PutDirectives = declare(null, {
		// summary:
		//		Directives passed to put() and add() handlers for guiding the update and
		//		creation of stored objects.
		// id: String|Number?
		//		Indicates the identity of the object if a new object is created
		// beforeId: String?
		//		If the collection of objects in the store has a natural ordering,
		//		this indicates that the created or updated object should be placed before the
		//		object whose identity is specified as the value of this property. A value of null indicates that the
		//		object should be last.
		// parent: Object?,
		//		If the store is hierarchical (with single parenting) this property indicates the
		//		new parent of the created or updated object.
		// overwrite: Boolean?
		//		If this is provided as a boolean it indicates that the object should or should not
		//		overwrite an existing object. A value of true indicates that a new object
		//		should not be created, the operation should update an existing object. A
		//		value of false indicates that an existing object should not be updated, a new
		//		object should be created (which is the same as an add() operation). When
		//		this property is not provided, either an update or creation is acceptable.
	});

	Store.Transaction = declare(null, {
		// summary:
		//		This is an object returned from transaction() calls that represents the current
		//		transaction.

		commit: function () {
			// summary:
			//		Commits the transaction. This may throw an error if it fails. Of if the operation
			//		is asynchronous, it may return a promise that represents the eventual success
			//		or failure of the commit.
		},
		abort: function (callback, thisObject) {
			// summary:
			//		Aborts the transaction. This may throw an error if it fails. Of if the operation
			//		is asynchronous, it may return a promise that represents the eventual success
			//		or failure of the abort.
		}
	});

	var __QueryLogEntry = {
		type: String
			The query type
		arguments: Array
			The original query arguments
		normalizedArguments: Array
			The normalized query arguments
		querier: Function?
			A client-side implementation of the query that takes an item array and returns an item array
	};
====*/
