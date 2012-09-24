define(["dojo/_base/kernel", "dojo/_base/declare", "dojo/_base/lang", "dojo/_base/Deferred", "dojo/on"],
function(kernel, declare, lang, Deferred, listen){
	// This module isolates the base logic required by store-aware list/grid
	// components, e.g. OnDemandList/Grid and the Pagination extension.
	
	function emitError(err){
		// called by _trackError in context of list/grid, if an error is encountered
		if(typeof err !== "object"){
			// Ensure we actually have an error object, so we can attach a reference.
			err = new Error(err);
		}
		err.grid = this;
		
		if(listen.emit(this.domNode, "dgrid-error", {error: err, cancelable: true, bubbles: true})){
			console.error(err);
		}
	}
	
	return declare(null, {
		// store: Object
		//		The object store (implementing the dojo/store API) from which data is
		//		to be fetched.
		store: null,
		
		// query: Object
		//		Specifies query parameter(s) to pass to store.query calls.
		query: null,
		
		// queryOptions: Object
		//		Specifies additional query options to mix in when calling store.query;
		//		sort, start, and count are already handled.
		queryOptions: null,
		
		// getBeforePut: boolean
		//		If true, a get request will be performed to the store before each put
		//		as a baseline when saving; otherwise, existing row data will be used.
		getBeforePut: true,
		
		// noDataMessage: String
		//		Message to be displayed when no results exist for a query.
		//		Defined by _StoreMixin, but to be implemented by subclasses.
		noDataMessage: "",
		
		// loadingMessage: String
		//		Message displayed when data is loading.
		//		Defined by _StoreMixin, but to be implemented by subclasses.
		loadingMessage: "",
		
		constructor: function(){
			// Create empty objects on each instance, not the prototype
			this.query = {};
			this.queryOptions = {};
			this.dirty = {};
			this._updating = {}; // tracks rows that are mid-update
		},
		
		_configColumn: function(column){
			// summary:
			//		Implements extension point provided by Grid to store references to
			//		any columns with `set` methods, for use during `save`.
			if (column.set){
				if(!this._columnsWithSet){ this._columnsWithSet = {}; }
				this._columnsWithSet[column.field] = column;
			}
		},
		
		_configColumns: function(){
			// summary:
			//		Extends Grid to reset _StoreMixin's hash when columns are updated
			this._columnsWithSet = null;
			return this.inherited(arguments);
		},
		
		_setStore: function(store, query, queryOptions){
			// summary:
			//		Assigns a new store (and optionally query/queryOptions) to the list,
			//		and tells it to refresh.
			this.store = store;
			this.dirty = {}; // discard dirty map, as it applied to a previous store
			this.set("query", query, queryOptions);
		},
		_setQuery: function(query, queryOptions){
			// summary:
			//		Assigns a new query (and optionally queryOptions) to the list,
			//		and tells it to refresh.
			
			var sort = queryOptions && queryOptions.sort;
			
			this.query = query !== undefined ? query : this.query;
			this.queryOptions = queryOptions || this.queryOptions;
			
			// If we have new sort criteria, pass them through sort
			// (which will update _sort and call refresh in itself).
			// Otherwise, just refresh.
			sort ? this.set("sort", sort) : this.refresh();
		},
		setStore: function(store, query, queryOptions){
			kernel.deprecated("setStore(...)", 'use set("store", ...) instead', "dgrid 1.0");
			this.set("store", store, query, queryOptions);
		},
		setQuery: function(query, queryOptions){
			kernel.deprecated("setQuery(...)", 'use set("query", ...) instead', "dgrid 1.0");
			this.set("query", query, queryOptions);
		},
		
		_getQueryOptions: function(){
			// summary:
			//		Get a fresh queryOptions object, also including the current sort
			var options = lang.delegate(this.queryOptions, {});
			if(this._sort.length){
				// Prevents SimpleQueryEngine from doing unnecessary "null" sorts (which can
				// change the ordering in browsers that don't use a stable sort algorithm, eg Chrome)
				options.sort = this._sort;
			}
			return options;
		},
		_getQuery: function(){
			// summary:
			//		Implemented consistent with _getQueryOptions so that if query is
			//		an object, this returns a protected (delegated) object instead of
			//		the original.
			var q = this.query;
			return typeof q == "object" && q != null ? lang.delegate(q, {}) : q;
		},
		
		_setSort: function(property, descending){
			// summary:
			//		Sort the content
			
			// prevent default storeless sort logic as long as we have a store
			if(this.store){ this._lastCollection = null; }
			this.inherited(arguments);
		},
		
		insertRow: function(object, parent, beforeNode, i, options){
			var store = this.store,
				dirty = this.dirty,
				id = store && store.getIdentity(object),
				dirtyObj;
			
			if(id in dirty && !(id in this._updating)){ dirtyObj = dirty[id]; }
			if(dirtyObj){
				// restore dirty object as delegate on top of original object,
				// to provide protection for subsequent changes as well
				object = lang.delegate(object, dirtyObj);
			}
			return this.inherited(arguments);
		},
		
		updateDirty: function(id, field, value){
			// summary:
			//		Updates dirty data of a field for the item with the specified ID.
			var dirty = this.dirty,
				dirtyObj = dirty[id];
			
			if(!dirtyObj){
				dirtyObj = dirty[id] = {};
			}
			dirtyObj[field] = value;
		},
		setDirty: function(id, field, value){
			kernel.deprecated("setDirty(...)", "use updateDirty() instead", "dgrid 1.0");
			this.updateDirty(id, field, value);
		},
		
		save: function() {
			// Keep track of the store and puts
			var self = this,
				store = this.store,
				dirty = this.dirty,
				dfd = new Deferred(), promise = dfd.promise,
				getFunc = function(id){
					// returns a function to pass as a step in the promise chain,
					// with the id variable closured
					var data;
					return (self.getBeforePut || !(data = self.row(id).data)) ?
						function(){ return store.get(id); } :
						function(){ return data; };
				};
			
			// function called within loop to generate a function for putting an item
			function putter(id, dirtyObj) {
				// Return a function handler
				return function(object) {
					var colsWithSet = self._columnsWithSet,
						updating = self._updating,
						key, data;
					// Copy dirty props to the original, applying setters if applicable
					for(key in dirtyObj){
						object[key] = dirtyObj[key];
					}
					if(colsWithSet){
						// Apply any set methods in column definitions.
						// Note that while in the most common cases column.set is intended
						// to return transformed data for the key in question, it is also
						// possible to directly modify the object to be saved.
						for(key in colsWithSet){
							data = colsWithSet[key].set(object);
							if(data !== undefined){ object[key] = data; }
						}
					}
					
					updating[id] = true;
					// Put it in the store, returning the result/promise
					return Deferred.when(store.put(object), function() {
						// Clear the item now that it's been confirmed updated
						delete dirty[id];
						delete updating[id];
					});
				};
			}
			
			// For every dirty item, grab the ID
			for(var id in dirty) {
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
		
		revert: function(){
			// summary:
			//		Reverts any changes since the previous save.
			this.dirty = {};
			this.refresh();
		},
		
		_trackError: function(func){
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
			
			var result;
			
			if(typeof func == "string"){ func = lang.hitch(this, func); }
			
			try{
				result = func();
			}catch(err){
				// report sync error
				emitError.call(this, err);
			}
			
			// wrap in when call to handle reporting of potential async error
			return Deferred.when(result, null, lang.hitch(this, emitError));
		}
	});
});
