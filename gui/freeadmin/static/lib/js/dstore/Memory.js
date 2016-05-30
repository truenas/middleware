define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/_base/array',
	'./Store',
	'./Promised',
	'./SimpleQuery',
	'./QueryResults'
], function (declare, lang, arrayUtil, Store, Promised, SimpleQuery, QueryResults) {

	// module:
	//		dstore/Memory
	return declare([Store, Promised, SimpleQuery ], {
		constructor: function () {
			// summary:
			//		Creates a memory object store.
			// options: dstore/Memory
			//		This provides any configuration information that will be mixed into the store.
			//		This should generally include the data property to provide the starting set of data.

			// Add a version property so subcollections can detect when they're using stale data
			this.storage.version = 0;
		},

		postscript: function () {
			this.inherited(arguments);

			// Set the data in `postscript` so subclasses can override `data` in their constructors
			// (e.g., a LocalStorage store that retrieves its data from localStorage)
			this.setData(this.data || []);
		},

		// data: Array
		//		The array of all the objects in the memory store
		data: null,

		autoEmitEvents: false, // this is handled by the methods themselves

		getSync: function (id) {
			// summary:
			//		Retrieves an object by its identity
			// id: Number
			//		The identity to use to lookup the object
			// returns: Object
			//		The object in the store that matches the given id.
			return this.storage.fullData[this.storage.index[id]];
		},
		putSync: function (object, options) {
			// summary:
			//		Stores an object
			// object: Object
			//		The object to store.
			// options: dstore/Store.PutDirectives?
			//		Additional metadata for storing the data.  Includes an 'id'
			//		property if a specific id is to be used.
			// returns: Number

			options = options || {};

			var storage = this.storage,
				index = storage.index,
				data = storage.fullData;

			var Model = this.Model;
			if (Model && !(object instanceof Model)) {
				// if it is not the correct type, restore a
				// properly typed version of the object. Note that we do not allow
				// mutation here
				object = this._restore(object);
			}
			var id = this.getIdentity(object);
			if (id == null) {
				this._setIdentity(object, ('id' in options) ? options.id : Math.random());
				id = this.getIdentity(object);
			}
			storage.version++;

			var eventType = id in index ? 'update' : 'add',
				event = { target: object },
				previousIndex,
				defaultDestination;
			if (eventType === 'update') {
				if (options.overwrite === false) {
					throw new Error('Object already exists');
				} else {
					data.splice(previousIndex = index[id], 1);
					defaultDestination = previousIndex;
				}
			} else {
				defaultDestination = this.defaultNewToStart ? 0 : data.length;
			}

			var destination;
			if ('beforeId' in options) {
				var beforeId = options.beforeId;

				if (beforeId === null) {
					destination = data.length;
				} else {
					destination = index[beforeId];

					// Account for the removed item
					if (previousIndex < destination) {
						--destination;
					}
				}

				if (destination !== undefined) {
					event.beforeId = beforeId;
				} else {
					console.error('options.beforeId was specified but no corresponding index was found');
					destination = defaultDestination;
				}
			} else {
				destination = defaultDestination;
			}
			data.splice(destination, 0, object);

			// the fullData has been changed, so the index needs updated
			var i = isFinite(previousIndex) ? Math.min(previousIndex, destination) : destination;
			for (var l = data.length; i < l; ++i) {
				index[this.getIdentity(data[i])] = i;
			}

			this.emit(eventType, event);

			return object;
		},
		addSync: function (object, options) {
			// summary:
			//		Creates an object, throws an error if the object already exists
			// object: Object
			//		The object to store.
			// options: dstore/Store.PutDirectives?
			//		Additional metadata for storing the data.  Includes an 'id'
			//		property if a specific id is to be used.
			// returns: Number
			(options = options || {}).overwrite = false;
			// call put with overwrite being false
			return this.putSync(object, options);
		},
		removeSync: function (id) {
			// summary:
			//		Deletes an object by its identity
			// id: Number
			//		The identity to use to delete the object
			// returns: Boolean
			//		Returns true if an object was removed, falsy (undefined) if no object matched the id
			var storage = this.storage;
			var index = storage.index;
			var data = storage.fullData;
			if (id in index) {
				var removed = data.splice(index[id], 1)[0];
				// now we have to reindex
				this._reindex();
				this.emit('delete', {id: id, target: removed});
				return true;
			}
		},
		setData: function (data) {
			// summary:
			//		Sets the given data as the source for this store, and indexes it
			// data: Object[]
			//		An array of objects to use as the source of data. Note that this
			//		array will not be copied, it is used directly and mutated as
			//		data changes.

			if (this.parse) {
				data = this.parse(data);
			}
			if (data.items) {
				// just for convenience with the data format ItemFileReadStore expects
				this.idProperty = data.identifier || this.idProperty;
				data = data.items;
			}
			var storage = this.storage;
			storage.fullData = this.data = data;
			this._reindex();
		},

		_reindex: function () {
			var storage = this.storage;
			var index = storage.index = {};
			var data = storage.fullData;
			var Model = this.Model;
			var ObjectPrototype = Object.prototype;
			for (var i = 0, l = data.length; i < l; i++) {
				var object = data[i];
				if (Model && !(object instanceof Model)) {
					var restoredObject = this._restore(object,
							// only allow mutation if it is a plain object
							// (which is generally the expected input),
							// if "typed" objects are actually passed in, we will
							// respect that, and leave the original alone
							object.__proto__ === ObjectPrototype);
					if (object !== restoredObject) {
						// a new object was generated in the restoration process,
						// so we have to update the item in the data array.
						data[i] = object = restoredObject;
					}
				}
				index[this.getIdentity(object)] = i;
			}
			storage.version++;
		},

		fetchSync: function () {
			var data = this.data;
			if (!data || data._version !== this.storage.version) {
				// our data is absent or out-of-date, so we requery from the root
				// start with the root data
				data = this.storage.fullData;
				var queryLog = this.queryLog;
				// iterate through the query log, applying each querier
				for (var i = 0, l = queryLog.length; i < l; i++) {
					data = queryLog[i].querier(data);
				}
				// store it, with the storage version stamp
				data._version = this.storage.version;
				this.data = data;
			}
			return new QueryResults(data);
		},

		fetchRangeSync: function (kwArgs) {
			var data = this.fetchSync(),
				start = kwArgs.start,
				end = kwArgs.end;
			return new QueryResults(data.slice(start, end), {
				totalLength: data.length
			});
		},

		_includePropertyInSubCollection: function (name) {
			return name !== 'data' && this.inherited(arguments);
		}
	});
});
