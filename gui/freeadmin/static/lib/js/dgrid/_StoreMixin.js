define([
	'dojo/_base/declare',
	'dojo/_base/lang',
	'dojo/Deferred',
	'dojo/aspect',
	'dojo/has',
	'dojo/on',
	'dojo/when',
	'put-selector/put'
], function (declare, lang, Deferred, aspect, has, on, when, put) {
	// This module isolates the base logic required by store-aware list/grid
	// components, e.g. OnDemandList/Grid and the Pagination extension.

	function emitError(err) {
		// called by _trackError in context of list/grid, if an error is encountered
		if (typeof err !== 'object') {
			// Ensure we actually have an error object, so we can attach a reference.
			err = new Error(err);
		}
		else if (err.dojoType === 'cancel') {
			// Don't fire dgrid-error events for errors due to canceled requests
			// (unfortunately, the Deferred instrumentation will still log them)
			return;
		}

		var event = on.emit(this.domNode, 'dgrid-error', {
			grid: this,
			error: err,
			cancelable: true,
			bubbles: true
		});
		if (event) {
			console.error(err);
		}
	}

	return declare(null, {
		// collection: Object
		//		The base object collection (implementing the dstore/api/Store API) before being sorted
		//		or otherwise processed by the grid. Use it for general purpose store operations such as
		//		`getIdentity` and `get`, `add`, `put`, and `remove`.
		collection: null,

		// _renderedCollection: Object
		//		The object collection from which data is to be fetched. This is the sorted collection.
		//		Use it when retrieving data to be rendered by the grid.
		_renderedCollection: null,

		// _rows: Array
		//		Sparse array of row nodes, used to maintain the grid in response to events from a tracked collection.
		//		Each node's index corresponds to the index of its data object in the collection.
		_rows: null,

		// _observerHandle: Object
		//		The observer handle for the current collection, if trackable.
		_observerHandle: null,

		// shouldTrackCollection: Boolean
		//		Whether this instance should track any trackable collection it is passed.
		shouldTrackCollection: true,

		// getBeforePut: boolean
		//		If true, a get request will be performed to the store before each put
		//		as a baseline when saving; otherwise, existing row data will be used.
		getBeforePut: true,

		// noDataMessage: String
		//		Message to be displayed when no results exist for a collection, whether at
		//		the time of the initial query or upon subsequent observed changes.
		//		Defined by _StoreMixin, but to be implemented by subclasses.
		noDataMessage: '',

		// loadingMessage: String
		//		Message displayed when data is loading.
		//		Defined by _StoreMixin, but to be implemented by subclasses.
		loadingMessage: '',

		_total: 0,

		constructor: function () {
			// Create empty objects on each instance, not the prototype
			this.dirty = {};
			this._updating = {}; // Tracks rows that are mid-update
			this._columnsWithSet = {};

			// Reset _columnsWithSet whenever column configuration is reset
			aspect.before(this, 'configStructure', lang.hitch(this, function () {
				this._columnsWithSet = {};
			}));
		},

		destroy: function () {
			this.inherited(arguments);

			if (this._renderedCollection) {
				this._cleanupCollection();
			}
		},

		_configColumn: function (column) {
			// summary:
			//		Implements extension point provided by Grid to store references to
			//		any columns with `set` methods, for use during `save`.
			if (column.set) {
				this._columnsWithSet[column.field] = column;
			}
			this.inherited(arguments);
		},

		_setCollection: function (collection) {
			// summary:
			//		Assigns a new collection to the list/grid, sets up tracking
			//		if applicable, and tells the list/grid to refresh.

			if (this._renderedCollection) {
				this.cleanup();
				this._cleanupCollection({
					// Only clear the dirty hash if the collection being used is actually from a different store
					// (i.e. not just a re-sorted / re-filtered version of the same store)
					shouldRevert: !collection || collection.storage !== this._renderedCollection.storage
				});
			}

			this.collection = collection;

			// Avoid unnecessary rendering and processing before the grid has started up
			if (this._started) {
				// Once startup is called, List.startup sets the sort property which calls _StoreMixin._applySort
				// which sets the collection property again.  So _StoreMixin._applySort will be executed again
				// after startup is called.
				if (collection) {
					var renderedCollection = collection;
					if (this.sort && this.sort.length > 0) {
						renderedCollection = collection.sort(this.sort);
					}

					if (renderedCollection.track && this.shouldTrackCollection) {
						renderedCollection = renderedCollection.track();
						this._rows = [];

						this._observerHandle = this._observeCollection(
							renderedCollection,
							this.contentNode,
							{ rows: this._rows }
						);
					}

					this._renderedCollection = renderedCollection;
				}
				this.refresh();
			}
		},

		_setStore: function () {
			if (!this.collection) {
				console.debug('set(\'store\') call detected, but you probably meant set(\'collection\') for 0.4');
			}
		},

		_getTotal: function () {
			// summary:
			//		Retrieves the currently-tracked total (as updated by
			//		subclasses after store queries, or by _StoreMixin in response to
			//		updated totalLength in events)

			return this._total;
		},

		_cleanupCollection: function (options) {
			// summary:
			//		Handles cleanup duty for the previous collection;
			//		called during _setCollection and destroy.
			// options: Object?
			//		* shouldRevert: Whether to clear the dirty hash

			options = options || {};

			if (this._renderedCollection.tracking) {
				this._renderedCollection.tracking.remove();
			}

			// Remove observer and existing rows so any sub-row observers will be cleaned up
			if (this._observerHandle) {
				this._observerHandle.remove();
				this._observerHandle = this._rows = null;
			}

			// Discard dirty map, as it applied to a previous collection
			if (options.shouldRevert !== false) {
				this.dirty = {};
			}

			this._renderedCollection = this.collection = null;
		},

		_applySort: function () {
			if (this.collection) {
				this.set('collection', this.collection);
			}
			else if (this.store) {
				console.debug('_StoreMixin found store property but not collection; ' +
					'this is often the sign of a mistake during migration from 0.3 to 0.4');
			}
		},

		row: function () {
			// Extend List#row with more appropriate lookup-by-id logic
			var row = this.inherited(arguments);
			if (row && row.data && typeof row.id !== 'undefined') {
				row.id = this.collection.getIdentity(row.data);
			}
			return row;
		},

		refresh: function () {
			var result = this.inherited(arguments);

			if (!this.collection) {
				this.noDataNode = put(this.contentNode, 'div.dgrid-no-data');
				this.noDataNode.innerHTML = this.noDataMessage;
			}

			return result;
		},

		renderArray: function () {
			var rows = this.inherited(arguments);

			if (!this.collection) {
				if (rows.length && this.noDataNode) {
					put(this.noDataNode, '!');
				}
			}
			return rows;
		},

		insertRow: function (object, parent, beforeNode, i, options) {
			var store = this.collection,
				dirty = this.dirty,
				id = store && store.getIdentity(object),
				dirtyObj,
				row;

			if (id in dirty && !(id in this._updating)) {
				dirtyObj = dirty[id];
			}
			if (dirtyObj) {
				// restore dirty object as delegate on top of original object,
				// to provide protection for subsequent changes as well
				object = lang.delegate(object, dirtyObj);
			}

			row = this.inherited(arguments);

			if (options && options.rows) {
				options.rows[i] = row;
			}

			// Remove no data message when a new row appears.
			// Run after inherited logic to prevent confusion due to noDataNode
			// no longer being present as a sibling.
			if (this.noDataNode) {
				put(this.noDataNode, '!');
				this.noDataNode = null;
			}

			return row;
		},

		updateDirty: function (id, field, value) {
			// summary:
			//		Updates dirty data of a field for the item with the specified ID.
			var dirty = this.dirty,
				dirtyObj = dirty[id];

			if (!dirtyObj) {
				dirtyObj = dirty[id] = {};
			}
			dirtyObj[field] = value;
		},

		save: function () {
			// Keep track of the store and puts
			var self = this,
				store = this.collection,
				dirty = this.dirty,
				dfd = new Deferred(),
				results = {},
				getFunc = function (id) {
					// returns a function to pass as a step in the promise chain,
					// with the id variable closured
					var data;
					return (self.getBeforePut || !(data = self.row(id).data)) ?
						function () {
							return store.get(id);
						} :
						function () {
							return data;
						};
				};

			// function called within loop to generate a function for putting an item
			function putter(id, dirtyObj) {
				// Return a function handler
				return function (object) {
					var colsWithSet = self._columnsWithSet,
						updating = self._updating,
						key, data;

					if (typeof object.set === 'function') {
						object.set(dirtyObj);
					} else {
						// Copy dirty props to the original, applying setters if applicable
						for (key in dirtyObj) {
							object[key] = dirtyObj[key];
						}
					}

					// Apply any set methods in column definitions.
					// Note that while in the most common cases column.set is intended
					// to return transformed data for the key in question, it is also
					// possible to directly modify the object to be saved.
					for (key in colsWithSet) {
						data = colsWithSet[key].set(object);
						if (data !== undefined) {
							object[key] = data;
						}
					}

					updating[id] = true;
					// Put it in the store, returning the result/promise
					return store.put(object).then(function (result) {
						// Clear the item now that it's been confirmed updated
						delete dirty[id];
						delete updating[id];
						results[id] = result;
						return results;
					});
				};
			}

			var promise = dfd.then(function () {
				// Ensure empty object is returned even if nothing was dirty, for consistency
				return results;
			});

			// For every dirty item, grab the ID
			for (var id in dirty) {
				// Create put function to handle the saving of the the item
				var put = putter(id, dirty[id]);

				// Add this item onto the promise chain,
				// getting the item from the store first if desired.
				promise = promise.then(getFunc(id)).then(put);
			}

			// Kick off and return the promise representing all applicable get/put ops.
			// If the success callback is fired, all operations succeeded; otherwise,
			// save will stop at the first error it encounters.
			dfd.resolve();
			return promise;
		},

		revert: function () {
			// summary:
			//		Reverts any changes since the previous save.
			this.dirty = {};
			this.refresh();
		},

		_trackError: function (func) {
			// summary:
			//		Utility function to handle emitting of error events.
			// func: Function|String
			//		A function which performs some store operation, or a String identifying
			//		a function to be invoked (sans arguments) hitched against the instance.
			//		If sync, it can return a value, but may throw an error on failure.
			//		If async, it should return a promise, which would fire the error
			//		callback on failure.
			// tags:
			//		protected

			if (typeof func === 'string') {
				func = lang.hitch(this, func);
			}

			var self = this,
				promise;

			try {
				promise = when(func());
			} catch (err) {
				// report sync error
				var dfd = new Deferred();
				dfd.reject(err);
				promise = dfd.promise;
			}

			promise.otherwise(function (err) {
				emitError.call(self, err);
			});
			return promise;
		},

		removeRow: function (rowElement, preserveDom, options) {
			var row = {element: rowElement};
			// Check to see if we are now empty...
			if (!preserveDom && this.noDataMessage &&
					(this.up(row).element === rowElement) &&
					(this.down(row).element === rowElement)) {
				// ...we are empty, so show the no data message.
				this.noDataNode = put(this.contentNode, 'div.dgrid-no-data');
				this.noDataNode.innerHTML = this.noDataMessage;
			}

			var rows = (options && options.rows) || this._rows;
			if (rows) {
				delete rows[rowElement.rowIndex];
			}

			return this.inherited(arguments);
		},

		renderQueryResults: function (results, beforeNode, options) {
			// summary:
			//		Renders objects from QueryResults as rows, before the given node.

			options = lang.mixin({ rows: this._rows }, options);
			var self = this;

			if (!has('dojo-built')) {
				// Check for null/undefined totalResults to help diagnose faulty services/stores
				results.totalLength.then(function (total) {
					if (total == null) {
						console.warn('Store reported null or undefined totalLength. ' +
							'Make sure your store (and service, if applicable) are reporting total correctly!');
					}
				});
			}

			return results.then(function (resolvedResults) {
				var resolvedRows = self.renderArray(resolvedResults, beforeNode, options);
				delete self._lastCollection; // used only for non-store List/Grid
				return resolvedRows;
			});
		},

		_observeCollection: function (collection, container, options) {
			var self = this,
				rows = options.rows,
				row;

			var handles = [
				collection.on('delete, update', function (event) {
					var from = event.previousIndex;
					var to = event.index;

					if (from !== undefined && rows[from]) {
						if ('max' in rows && (to === undefined || to < rows.min || to > rows.max)) {
							rows.max--;
						}

						row = rows[from];

						// check to make the sure the node is still there before we try to remove it
						// (in case it was moved to a different place in the DOM)
						if (row.parentNode === container) {
							self.removeRow(row, false, options);
						}

						// remove the old slot
						rows.splice(from, 1);

						if (event.type === 'delete' ||
								(event.type === 'update' && (from < to || to === undefined))) {
							// adjust the rowIndex so adjustRowIndices has the right starting point
							rows[from] && rows[from].rowIndex--;
						}
					}
					if (event.type === 'delete') {
						// Reset row in case this is later followed by an add;
						// only update events should retain the row variable below
						row = null;
					}
				}),

				collection.on('add, update', function (event) {
					var from = event.previousIndex;
					var to = event.index;
					var nextNode;

					function advanceNext() {
						nextNode = (nextNode.connected || nextNode).nextSibling;
					}

					// When possible, restrict observations to the actually rendered range
					if (to !== undefined && (!('max' in rows) || (to >= rows.min && to <= rows.max))) {
						if ('max' in rows && (from === undefined || from < rows.min || from > rows.max)) {
							rows.max++;
						}
						// Add to new slot (either before an existing row, or at the end)
						// First determine the DOM node that this should be placed before.
						if (rows.length) {
							nextNode = rows[to];
							if (!nextNode) {
								nextNode = rows[to - 1];
								if (nextNode) {
									// Make sure to skip connected nodes, so we don't accidentally
									// insert a row in between a parent and its children.
									advanceNext();
								}
							}
						}
						else {
							// There are no rows.  Allow for subclasses to insert new rows somewhere other than
							// at the end of the parent node.
							nextNode = self._getFirstRowSibling && self._getFirstRowSibling(container);
						}
						// Make sure we don't trip over a stale reference to a
						// node that was removed, or try to place a node before
						// itself (due to overlapped queries)
						if (row && nextNode && row.id === nextNode.id) {
							advanceNext();
						}
						if (nextNode && !nextNode.parentNode) {
							nextNode = document.getElementById(nextNode.id);
						}
						rows.splice(to, 0, undefined);
						row = self.insertRow(event.target, container, nextNode, to, options);
						self.highlightRow(row);
					}
					// Reset row so it doesn't get reused on the next event
					row = null;
				}),

				collection.on('add, delete, update', function (event) {
					var from = (typeof event.previousIndex !== 'undefined') ? event.previousIndex : Infinity,
						to = (typeof event.index !== 'undefined') ? event.index : Infinity,
						adjustAtIndex = Math.min(from, to);
					from !== to && rows[adjustAtIndex] && self.adjustRowIndices(rows[adjustAtIndex]);

					// the removal of rows could cause us to need to page in more items
					if (from !== Infinity && self._processScroll && (rows[from] || rows[from - 1])) {
						self._processScroll();
					}

					// Fire _onNotification, even for out-of-viewport notifications,
					// since some things may still need to update (e.g. Pagination's status/navigation)
					self._onNotification(rows, event, collection);

					// Update _total after _onNotification so that it can potentially
					// decide whether to perform actions based on whether the total changed
					if (collection === self._renderedCollection && 'totalLength' in event) {
						self._total = event.totalLength;
					}
				})
			];

			return {
				remove: function () {
					while (handles.length > 0) {
						handles.pop().remove();
					}
				}
			};
		},

		_onNotification: function () {
			// summary:
			//		Protected method called whenever a store notification is observed.
			//		Intended to be extended as necessary by mixins/extensions.
			// rows: Array
			//		A sparse array of row nodes corresponding to data objects in the collection.
			// event: Object
			//		The notification event
			// collection: Object
			//		The collection that the notification is relevant to.
			//		Useful for distinguishing child-level from top-level notifications.
		}
	});
});
