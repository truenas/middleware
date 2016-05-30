define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/Deferred',
	'dojo/when',
	'dojo/promise/all',
	'dstore/Store',
	'dstore/SimpleQuery',
	'dstore/QueryResults'
], function (declare, lang, Deferred, when, all, Store, SimpleQuery, QueryResults) {

	function makePromise(request) {
		var deferred = new Deferred();
		request.onsuccess = function (event) {
			deferred.resolve(event.target.result);
		};
		request.onerror = function () {
			request.error.message = request.webkitErrorMessage;
			deferred.reject(request.error);
		};
		return deferred.promise;
	}

	// we keep a queue of cursors, so we can prioritize the traversal of result sets
	var cursorQueue = [];
	var maxConcurrent = 1;
	var cursorsRunning = 0;
	function queueCursor(cursor, priority, retry) {
		// process the cursor queue, possibly submitting a cursor for continuation
		if (cursorsRunning || cursorQueue.length) {
			// actively processing
			if (cursor) {
				// add to queue
				cursorQueue.push({cursor: cursor, priority: priority, retry: retry});
				// keep the queue in priority order
				cursorQueue.sort(function(a, b) {
					return a.priority > b.priority ? 1 : -1;
				});
			}
			if (cursorsRunning >= maxConcurrent) {
				return;
			}
			var cursorObject = cursorQueue.pop();
			cursor = cursorObject && cursorObject.cursor;
		}//else nothing in the queue, just shortcut directly to continuing the cursor
		if (cursor) {
			try {
				// submit the continuation of the highest priority cursor
				cursor['continue']();
				cursorsRunning++;
			} catch(e) {
				if ((e.name === 'TransactionInactiveError' || e.name === 0) && cursorObject) { // == 0 is IndexedDBShim
					// if the cursor has been interrupted we usually need to create a new transaction, 
					// handing control back to the query/filter function to open the cursor again
					cursorObject.retry();
				} else {
					throw e;
				}
			}
		}
	}
	function yes() {
		return true;
	}


	var IDBKeyRange = window.IDBKeyRange || window.webkitIDBKeyRange;
	return declare([Store, SimpleQuery], {
		// summary:
		//		This is a basic store for IndexedDB. It implements dojo/store/api/Store.

		constructor: function (options) {
			// summary:
			//		This is a basic store for IndexedDB.
			// options:
			//		This provides any configuration information that will be mixed into the store

			declare.safeMixin(this, options);
			var store = this;
			var dbConfig = this.dbConfig;
			this.indices = dbConfig.stores[this.storeName];
			this.cachedCount = {};
			for (var index in store.indices) {
				var value = store.indices[index];
				if (typeof value === 'number') {
					store.indices[index] = {
						preference: value
					};
				}
			}
			this.db = this.db || dbConfig.db;

			if (!this.db) {
				var openRequest = dbConfig.openRequest;
				if (!openRequest) {
					openRequest = dbConfig.openRequest = window.indexedDB.open(dbConfig.name || 'dojo-db',
						parseInt(dbConfig.version, 10));
					openRequest.onupgradeneeded = function () {
						var db = store.db = openRequest.result;
						for (var storeName in dbConfig.stores) {
							var storeConfig = dbConfig.stores[storeName];
							if (!db.objectStoreNames.contains(storeName)) {
								var idProperty = storeConfig.idProperty || 'id';
								var idbStore = db.createObjectStore(storeName, {
									keyPath: idProperty,
									autoIncrement: storeConfig[idProperty] &&
										storeConfig[idProperty].autoIncrement || false
								});
							} else {
								idbStore = openRequest.transaction.objectStore(storeName);
							}
							for (var index in storeConfig) {
								if (!idbStore.indexNames.contains(index) && index !== 'autoIncrement' &&
										storeConfig[index].indexed !== false) {
									idbStore.createIndex(index, index, storeConfig[index]);
								}
							}
						}
					};
					dbConfig.db = makePromise(openRequest);
				}
				this.db = dbConfig.db.then(function(db) {
					return (store.db = db);
				});
			}
		},

		// idProperty: String
		//		Indicates the property to use as the identity property. The values of this
		//		property should be unique.
		idProperty: 'id',

		storeName: '',

		// indices:
		//		a hash of the preference of indices, indices that are likely to have very
		//		unique values should have the highest numbers
		//		as a reference, sorting is always set at 1, so properties that are higher than
		//		one will trigger filtering with index and then sort the whole set.
		//		we recommend setting boolean values at 0.1.
		indices: {
			/*
			property: {
				preference: 1,
				multiEntry: true
			}
			*/
		},

		transaction: function () {
			var store = this;
			this._currentTransaction = null;// get rid of the last transaction
			return {
				abort: function () {
					store._currentTransaction.abort();
				},
				commit: function () {
					// noop, idb does auto-commits
					store._currentTransaction = null;// get rid of the last transaction
				}
			};
		},

		_getTransaction: function () {
			if (!this._currentTransaction) {
				if (!this.db) {
					console.error('The database has not been initialized yet');
				}
				this._currentTransaction = this.db.transaction([this.storeName], 'readwrite');
				var store = this;
				this._currentTransaction.oncomplete = function () {
					// null it out so we will use a new one next time
					store._currentTransaction = null;
				};
				this._currentTransaction.onerror = function (error) {
					console.error(error);
				};
			}
			return this._currentTransaction;
		},

		_callOnStore: function (method, args, index, returnRequest) {
			// calls a method on the IndexedDB store
			var store = this;
			return when(this.db, function callOnStore(db) {
				if (store.db.then) {
					// replace the promise with the database itself
					store.db = db;
				}
				var currentTransaction = store._currentTransaction;
				if (currentTransaction) {
					var allowRetry = true;
				} else {
					currentTransaction = store._getTransaction();
				}
				var request, idbStore;
				if (allowRetry) {
					try {
						idbStore = currentTransaction.objectStore(store.storeName);
						if (index) {
							idbStore = idbStore.index(index);
						}
						request = idbStore[method].apply(idbStore, args);
					} catch(e) {
						if (e.name === 'TransactionInactiveError' || e.name === 'InvalidStateError') {
							store._currentTransaction = null;
							//retry
							return callOnStore();
						} else {
							throw e;
						}
					}
				} else {
					idbStore = currentTransaction.objectStore(store.storeName);
					if (index) {
						idbStore = idbStore.index(index);
					}
					request = idbStore[method].apply(idbStore, args);
				}
				return returnRequest ? request : makePromise(request);
			});
		},

		get: function (id) {
			// summary:
			//		Retrieves an object by its identity.
			// id: Number
			//		The identity to use to lookup the object
			// options: Object?
			// returns: dojo//Deferred
			var store = this;
			return this._callOnStore('get',[id]).then(function (object) {
				return store._restore(object);
			});
		},

		getIdentity: function (object) {
			// summary:
			//		Returns an object's identity
			// object: Object
			//		The object to get the identity from
			// returns: Number

			return object[this.idProperty];
		},

		put: function (object, options) {
			// summary:
			//		Stores an object.
			// object: Object
			//		The object to store.
			// options: __PutDirectives?
			//		Additional metadata for storing the data.  Includes an "id"
			//		property if a specific id is to be used.
			// returns: dojo/Deferred

			options = options || {};
			this.cachedCount = {}; // clear the count cache
			var store = this;
			return this._callOnStore(options.overwrite === false ? 'add' : 'put',[object])
				.then(function (object) {
					return store._restore(object);
				});
		},

		add: function (object, options) {
			// summary:
			//		Adds an object.
			// object: Object
			//		The object to store.
			// options: __PutDirectives?
			//		Additional metadata for storing the data.  Includes an "id"
			//		property if a specific id is to be used.
			// returns: dojo/Deferred

			options = options || {};
			options.overwrite = false;
			return this.put(object, options);
		},

		remove: function (id) {
			// summary:
			//		Deletes an object by its identity.
			// id: Number
			//		The identity to use to delete the object
			// returns: dojo/Deferred

			this.cachedCount = {}; // clear the count cache
			return this._callOnStore('delete', [id]);
		},

		fetch: function () {
			return this._fetch(yes);
		},

		fetchRange: function (range) {
			return this._fetch(yes, range);
		},

		forEach: function (callback, thisObject) {
			return this._fetch(function (object, index) {
				callback.call(thisObject, object, index);
			});
		},

		_union: function (query, callback, fetchOptions) {
			// perform a union query
			fetchOptions = fetchOptions || {};
			var start = fetchOptions.start || 0;
			var end = fetchOptions.end || Infinity;
			var sortOption = query.sort;
			var select = query.select;
			var parts = query.filter;
			var sorter, sortOptions;
			if (sortOption) {
				sortOptions = {sort: sortOption};
				sorter = this._createSortQuerier(sortOptions);
			} else {
				sorter = function (data) {
					// no sorting
					return data;
				};
			}
			var totals = [];
			var collectedCount = 0;
			var inCount = 0;
			var index = 0;
			var queues = [];
			var done;
			var collected = {};
			var results = [];
			var store = this;
			// wait for all the union segments to complete
			return new QueryResults(when(parts).then(
				function(parts){
					return all(parts.map(function(part, i) {
						var queue = queues[i] = [];

						function addToQueue(object) {
							// to the queue that is kept for each individual query for merge sorting
							queue.push(object);
							var nextInQueues = []; // so we can index of the selected choice
							var toMerge = [];
							while (queues.every(function(queue) {
									if (queue.length > 0) {
										var next = queue[0];
										if (next) {
											toMerge.push(next);
										}
										return nextInQueues.push(next);
									}
								})) {
								if (index >= end || toMerge.length === 0) {
									done = true;
									return; // exit filter loop
								}
								var nextSelected = sorter(toMerge)[0];
								// shift it off the selected queue
								queues[nextInQueues.indexOf(nextSelected)].shift();
								if (index++ >= start) {
									results.push(nextSelected);
									if (!callback(nextSelected)) {
										done = true;
										return;
									}
								}
								nextInQueues = [];// reset
								toMerge = [];
							}
							return true;

						}
						var queryResults = store._query({
							filterFunction: query.filterFunction,
							filter: part,
							sort: sortOption
						}, function (object) {
							if (done) {
								return;
							}
							var id = store.getIdentity(object);
							inCount++;
							if (id in collected) {
								return true;
							}
							collectedCount++;
							collected[id] = true;
							return addToQueue(object);
						});
						totals[i] = queryResults.totalLength;
						return queryResults.then(function(results) {
							// null signifies the end of this particular query result
							addToQueue(null);
							return results;
						});
					}));
				}
			).then(function() {
				if (select) {
					return select.querier(results);
				}
				return results;
			}), {
				totalLength: {
					then: function () {
						// do it lazily again
						return all(totals).then(function(totals) {
							return totals.reduce(function(a, b) {
								return a + b;
							}) * collectedCount / (inCount || 1);
						}).then.apply(this, arguments);
					}
				}
			});
		},
		_normalizeQuery: function () {
			// normalize the operators to a single query object
			var filter;
			var union;
			var filterQuery = {};
			var filterOperator;
			var sortOption;
			var select;
			var filterPromises = [];
			// iterate through the query log, applying each querier
			this.queryLog.forEach(function (entry) {
				var type = entry.type;
				var args = entry.normalizedArguments;
				if (type === 'filter') {
					filterOperator = args;
					var oldFilter = filter;
					filter = oldFilter ? function (data) {
						return entry.querier(oldFilter(data));
					} : entry.querier;

					processFilter(args, true);
				} else if (type === 'sort') {
					sortOption = args[0];
					sortOption.querier = entry.querier;
				} else if (type === 'select') {
					select = entry;
				}
			});

			function processFilter(filterArgs) {
				// iterate through the query log, applying each querier
				filterArgs.forEach(function processFilterArg(entry) {
					if (union) {
						throw new Error('Can not process conditions after a union, rearrange the query with the union last');
					}
					var type = entry.type;
					var args = [].slice.call(entry.args, 0);
					var name = args[0];
					var value = args[1];
					if (value && value.fetch && !value.data) {
						// the value is a collection, we will fetch it
						filterPromises.push(value.fetch().then(function (fetched) {
							value.data = fetched;
							processFilterArg(entry);
						}, function (error) {
							console.error('Failed to retrieved nested collection', error);
						}));
						return;
					}
					if (type === 'or') {
						or(args);
					} else if (type === 'and') {
						processFilter(args);
					} else if (type === 'eq') {
						addCondition(name, value);
					} else if (type === 'gt' || type === 'gte') {
						var filterProperty = filterQuery[name] || (filterQuery[name] = {});
						filterProperty.from = value;
						filterProperty.excludeFrom = type === 'gt';
						addCondition(name, filterProperty);
					} else if (type === 'lt' || type === 'lte') {
						var filterProperty = filterQuery[name] || (filterQuery[name] = {});
						filterProperty.to = value;
						filterProperty.excludeTo = type === 'lt';
						addCondition(name, filterProperty);
					} else if (type === 'in') {
						// split this into a union of equals
						or((value.data || value).map(function (item) {
							return {
								type: 'eq',
								args: [name, item]
							};
						}));
					} else if (type === 'contains') {
						var filterProperty = filterQuery[name] || (filterQuery[name] = {});
						filterProperty.contains = value.data ? value.data : value instanceof Array ? value : [value];
						addCondition(name, filterProperty);
					} else if (type === 'match') {
						value = value.source;
						if (value[0] === '^' && !value.match(/[\{\}\(\)\[\]\.\,\$\*]/)) {
							var filterProperty = filterQuery[name] || (filterQuery[name] = {});
							value = value.slice(1);
							filterProperty.from = value;
							filterProperty.to = value + '~';
							addCondition(name, filterProperty);
						} else {
							throw new Error('The match filter only supports simple prefix matching like /^starts with/');
						}
					} else {
						throw new Error('Unsupported filter type "' + type + '"');
					}
				});
			}

			filter = filter || function (data) {
				return data;
			};
			// an array, do a union (note that indexeddb only runs on modern browsers)
			function or(args) {
				union = args.map(function (arg) {
					filterQuery = {};
					processFilter([arg]);
					return filterQuery;
				});
			}
			function addCondition(key, filterValue) {
				// test all the filters as possible indices to drive the query
				var range = false;

				if (typeof filterValue === 'boolean') {
					// can't use booleans as filter keys
					return;
				}

				if (filterValue) {
					if (filterValue.from || filterValue.to) {
						range = true;
						(function(from, to) {
							// convert a to/from object to a testable object with a keyrange
							filterValue.test = function (value) {
								return !from || from <= value &&
										(!to || to >= value);
							};
							filterValue.keyRange = from ?
										  to ?
										  IDBKeyRange.bound(from, to, filterValue.excludeFrom, filterValue.excludeTo) :
										  IDBKeyRange.lowerBound(from, filterValue.excludeFrom) :
										  IDBKeyRange.upperBound(to, filterValue.excludeTo);
						})(filterValue.from, filterValue.to);
					} else if (typeof filterValue === 'object' && filterValue.contains) {
						// contains is for matching any value in a given array to any value in the target indices array
						// this expects a multiEntry: true index
						(function(contains) {
							var keyRange, first = contains[0];
							if (typeof first === 'object' && first.type === 'match') {
								if (first.args[1].source[0] === '^') {
									var value = first.args[1].source.slice(1);
									keyRange = IDBKeyRange.bound(value, value + '~');
								}
							} else {
								keyRange = IDBKeyRange.only(first);
							}
							filterValue.test = function (value) {
								return contains.every(function(item) {
									if (typeof item === 'object' && item.type === 'match') {
										// regular expression
										var regex = item.args[1];
										return value.some(function (value) {
											return !!regex.test(value);
										});
									}
									return value && value.indexOf(item) > -1;
								} );
							};
							filterValue.keyRange = keyRange;
						})(filterValue.contains);
					}
				}
				filterQuery[key] = filterValue;
			}
			return {
				filter: filterPromises.length > 0 ? all(filterPromises).then(function () {
					return union;
				}) : (union || filterQuery),
				filterFunction: filter,
				filterOperator: filterOperator || null,
				sort: sortOption,
				select: select
			};
		},
		_fetch: function (callback, fetchOptions) {
			var query = this._normalizeQuery();
			var filterQuery = query.filter;
			var store = this;
			if (filterQuery instanceof Array || filterQuery.then) {
				return this._union(query, function (object) {
					callback(store._restore(object));
					// keep going
					return true;
				}, fetchOptions);
			}
			return this._query(query, function (object) {
				callback(store._restore(object));
				// keep going
				return true;
			}, fetchOptions);
		},
		_query: function (query, callback, fetchOptions) {
			// summary:
			//		Queries the store for objects.
			// query: Object
			//		The query to use for retrieving objects from the store.

			fetchOptions = fetchOptions || {};
			var store = this;
			var start = fetchOptions.start || 0;
			var end = fetchOptions.end || Infinity;
			var keyRange;
			var alreadySearchedProperty;
			var advance;
			var bestIndex, bestIndexQuality = 0;
			var indexTries = 0;
			var filterValue;
			var deferred = new Deferred();
			var resultsPromise = deferred.promise;
			var filter = query.filterFunction;
			var filterQuery = query.filter;
			var sortOption = query.sort;
			var select = query.select;

			function tryIndex(indexName, quality, factor) {
				indexTries++;
				var indexDefinition = store.indices[indexName];
				if (indexDefinition && indexDefinition.indexed !== false) {
					quality = quality || indexDefinition.preference * (factor || 1) || 0.001;
					if (quality > bestIndexQuality) {
						bestIndexQuality = quality;
						bestIndex = indexName;
						return true;
					}
				}
				indexTries++;
			}
			for (var key in filterQuery) {
				var value = filterQuery[key];
				tryIndex(key, null, value && (value.from || value.to) ? 0.1 : 1);
			}
			var queryId = JSON.stringify(query.filterOperator) + '-' + JSON.stringify(sortOption);

			var descending;
			if (sortOption) {
				// this isn't necessarily the best heuristic to determine the best index
				var mainSort = sortOption[0];
				if (mainSort.property === bestIndex || tryIndex(mainSort.property, 1)) {
					descending = mainSort.descending;
				} else {
					// we need to sort afterwards now
					var postSorting = true;
					// we have to retrieve everything in this case
					start = 0;
					end = Infinity;
				}
			}
			var cursorRequestArgs;
			if (bestIndex) {
				if (bestIndex in filterQuery) {
					// we are filtering
					filterValue = filterQuery[bestIndex];
					if (filterValue && (filterValue.keyRange)) {
						keyRange = filterValue.keyRange;
					} else {
						keyRange = IDBKeyRange.only(filterValue);
					}
					alreadySearchedProperty = bestIndex;
				} else {
					keyRange = null;
				}
				cursorRequestArgs = [keyRange, descending ? 'prev' : 'next'];
			} else {
				// no index, no arguments required
				cursorRequestArgs = [];
			}

			var cachedPosition = store.cachedPosition;
			if (cachedPosition && cachedPosition.queryId === queryId &&
					cachedPosition.offset < start && indexTries > 1) {
				advance = cachedPosition.preFilterOffset + 1;
				// make a new copy, so we don't have concurrency issues
				store.cachedPosition = cachedPosition = lang.mixin({}, cachedPosition);
			} else {
				// cache of the position, tracking our traversal progress
				cachedPosition = store.cachedPosition = {
					offset: -1,
					preFilterOffset: -1,
					queryId: queryId
				};
				if (indexTries < 2) {
					// can skip to advance
					cachedPosition.offset = cachedPosition.preFilterOffset = (advance = start) - 1;
				}
			}
			// this is adjusted so we can compute the total more accurately
			var totalLength = {
				then: function (callback, errback) {
					// make this a lazy promise, only executing if we need to
					var cachedCount = store.cachedCount[queryId];
					if (cachedCount) {
						return callback(adjustTotal(cachedCount));
					} else {
						if (cachedPosition.finished) {
							// we have aleady finished traversing the results, can provide the exact count immediately
							var deferred = new Deferred();
							deferred.resolve(cachedPosition.offset + 1);
							return deferred.then(callback);
						}
						var countPromise = (keyRange ? store._callOnStore('count', [keyRange], bestIndex) : store._callOnStore('count'));
						return countPromise.then(adjustTotal).then(callback, errback);
					}
					function adjustTotal(total) {
						// we estimate the total count base on the matching rate
						store.cachedCount[queryId] = total;
						return Math.round((cachedPosition.offset + 1.01) / (cachedPosition.preFilterOffset + 1.01) * total);
					}
				}
			};
			// this is main implementation of the the query results traversal, forEach and map use this method
			var all = [];
			function openCursor() {
				// get the cursor
				when(store._callOnStore('openCursor', cursorRequestArgs, bestIndex, true), function (cursorRequest) {
					// this will be called for each iteration in the traversal
					cursorsRunning++;
					cursorRequest.onsuccess = function (event) {
						cursorsRunning--;
						var cursor = event.target.result;
						if (cursor) {
							if (advance) {
								// we can advance through and wait for the completion
								cursor.advance(advance);
								cursorsRunning++;
								advance = false;
								return;
							}
							cachedPosition.preFilterOffset++;
							try {
								var item = cursor.value;
								if (fetchOptions.join) {
									item = fetchOptions.join(item);
								}
								return when(item, function (item) {
									if (filter([item]).length > 0) {
										cachedPosition.offset++;
										if (cachedPosition.offset >= start) { // make sure we are after the start
											all.push(item);
											if (!callback(item, cachedPosition.offset - start) ||
													cachedPosition.offset >= end - 1) {
												// finished
												cursorRequest.lastCursor = cursor;
												deferred.resolve(all);
												queueCursor();
												return;
											}
										}
									}
									// submit our cursor to the priority queue for continuation, now or when our turn comes up
									return queueCursor(cursor, fetchOptions.priority, function () {
										// retry function, that we provide to the queue to use
										// if the cursor can't be continued due to interruption
										// if called, open the cursor again, and continue from our current position
										advance = cachedPosition.preFilterOffset;
										openCursor();
									});
								});
							} catch(e) {
								deferred.reject(e);
							}
						} else {
							if (!start || cachedPosition.offset >= start) {
								cachedPosition.finished = true;
							}
							deferred.resolve(all);
						}
						// let any other cursors start executing now
						queueCursor();
					};
					cursorRequest.onerror = onCursorError;
				}, onCursorError);
				function onCursorError(error) {
					cursorsRunning--;
					deferred.reject(error);
					queueCursor();
				}
			}
			openCursor();

			if (postSorting) {
				// we are using the index to do filtering, so we are going to have to sort the entire list
				// we have to redirect the callback
				var sortedCallback = callback;
				callback = yes;
				var resultsPromise = resultsPromise.then(function (filteredResults) {
					// now apply the sort and reapply the range
					var start = fetchOptions.start || 0;
					var end = fetchOptions.end || Infinity;
					var sorted = sortOption.querier(filteredResults).slice(start, end);
					sorted.forEach(sortedCallback);
					return sorted;
				});
			}
			if (select) {
				resultsPromise = resultsPromise.then(function(results) {
					return select.querier(results);
				});
			}
			return new QueryResults(resultsPromise, {totalLength: totalLength});
		}
	});

});
