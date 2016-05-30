define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/_base/array',
	'dojo/when',
	'../Store',
	'../QueryResults'
], function (declare, lang, arrayUtil, when, Store, QueryResults) {
// module:
//		An adapter mixin that makes a legacy Dojo object store look like a dstore object.

	var modifyDelegate = function (name) {
		return function () {
			var objectStore = this.objectStore;
			return objectStore[name].apply(objectStore, arguments);
		};
	};

	return declare(Store, {

		// objectStore:
		//		The object store wrapped by this adapter
		objectStore: null,

		get: function () {
			// summary:
			//		Retrieves an object by its identity
			// id: Number
			//		The identity to use to lookup the object
			// returns: Object
			//		The object in the store that matches the given id.
			var self = this,
				objectStore = this.objectStore;
			return when(objectStore.get.apply(objectStore, arguments), function (object) {
				return self._restore(object);
			});
		},

		put: modifyDelegate('put'),
		add: modifyDelegate('add'),
		remove: modifyDelegate('remove'),

		getIdentity: modifyDelegate('getIdentity'),

		_setIdentity: function (object, identityArg) {
			return (object[this.objectStore.idProperty] = identityArg);
		},

		fetch: function () {
			// summary:
			//		Fetches the query results. Note that the fetch may occur asynchronously
			// returns: Array|Promise
			//		The results or a promise for the results

			// create an object store query and query options based on current collection
			// information
			return this.fetchRange();
		},

		fetchRange: function (rangeArgs) {
			// summary:
			//		Fetches the query results with a range. Note that the fetch may occur asynchronously
			// returns: Array|Promise
			//		The results or a promise for the results

			// create an object store query and query options based on current collection
			// information
			var queryOptions = {},
				queryLog = this.queryLog,
				getQueryArguments = function (type) {
					return arrayUtil.map(
						arrayUtil.filter(queryLog, function (entry) { return entry.type === type; }),
						function (entry) {
							return entry.normalizedArguments[0];
						}
					);
				};

			// take the last sort since multiple sorts are not supported by dojo/store
			var sorted = getQueryArguments('sort').pop();
			if (sorted) {
				queryOptions.sort = sorted;

				if (sorted instanceof Array) {
					// object stores expect an attribute property
					for (var i = 0; i < sorted.length; i++) {
						var sortSegment = sorted[i];
						sortSegment.attribute = sortSegment.property;
					}
				}
			}
			if (rangeArgs) {
				// set the range
				queryOptions.count = rangeArgs.end - ((queryOptions.start = rangeArgs.start) || 0);
			}

			var queryObject = {};
			applyFilter(getQueryArguments('filter'));

			function applyFilter(filtered) {
				for (var i = 0; i < filtered.length; i++) {
					var filter = filtered[i];
					var type = filter.type;
					var args = filter.args;
					if (type === 'and') {
						applyFilter(args);
					} else if (type === 'eq' || type === 'match') {
						queryObject[args[0]] = args[1];
					} else if (type === 'string') {
						queryObject = args[0];
					} else if (type) {
						throw new Error('"' + type + ' operator can not be converted to a legacy store query');
					}
					// else if (!type) { no-op }
				}
			}

			var results = this.objectStore.query(queryObject, queryOptions);
			if (results) {
				// apply the object restoration
				return new QueryResults(when(results.map(this._restore, this)), {
					totalLength: when(results.total)
				});
			}
			return when(results);
		}
	});
});
