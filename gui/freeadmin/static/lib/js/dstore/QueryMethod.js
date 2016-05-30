define([], function () {
	/*=====
	var __QueryMethodArgs = {
		// type: String
		//		The type of the query. This identifies the query's type in the query log
		//		and the name of the corresponding query engine method.
		// normalizeArguments: Function?
		//		A function that normalizes arguments for consumption by a query engine
		// applyQuery: Function?
		//		A function that takes the query's new subcollection and the query's log entry
		//		and applies it to the new subcollection. This is useful for collections that need
		//		to both declare and implement new query methods.
		// querierFactory: Function?
		//		A factory function that provides a default querier implementation to use when
		//		a collection does not define its own querier factory method for this query type.
	};
	=====*/
	return function QueryMethod(/*__QueryMethodArgs*/ kwArgs) {
		// summary:
		//		The constructor for a dstore collection query method
		// description:
		//		This is the constructor for a collection query method. It encapsulates the following:
		//		* Creating a new subcollection for the query results
		//		* Logging the query in the collection's `queryLog`
		//		* Normalizing query arguments
		//		* Applying the query engine
		// kwArgs:
		//		The properties that define the query method
		// returns: Function
		//		Returns a function that takes query arguments and returns a new collection with
		//		the query associated with it.

		var type = kwArgs.type,
			normalizeArguments = kwArgs.normalizeArguments,
			applyQuery = kwArgs.applyQuery,
			defaultQuerierFactory = kwArgs.querierFactory;

		return function () {
			// summary:
			//		A query method whose arguments are determined by the query type
			// returns: dstore/Collection
			//		A collection representing the query results

			var originalArguments = Array.prototype.slice.call(arguments),
				normalizedArguments = normalizeArguments
					? normalizeArguments.apply(this, originalArguments)
					: originalArguments,
				logEntry = {
					type: type,
					arguments: originalArguments,
					normalizedArguments: normalizedArguments
				},
				querierFactory = this._getQuerierFactory(type) || defaultQuerierFactory;

			if (querierFactory) {
				// Call the query factory in store context to support things like
				// mapping a filter query's string argument to a custom filter method on the collection
				logEntry.querier = querierFactory.apply(this, normalizedArguments);
			}

			var newCollection = this._createSubCollection({
				queryLog: this.queryLog.concat(logEntry)
			});

			return applyQuery ? applyQuery.call(this, newCollection, logEntry) : newCollection;
		};
	};
});
