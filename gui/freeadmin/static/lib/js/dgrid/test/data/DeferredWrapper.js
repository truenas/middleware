define(["dojo/_base/lang", "dojo/_base/Deferred", "dojo/store/util/QueryResults"],function(lang, Deferred, QueryResults){
	// summary:
	//		Creates a store that wraps the delegate store's query results and total in Deferred
	//		instances. If delay is set, the Deferreds will be resolved asynchronously after delay +/-50%
	//		milliseconds to simulate network requests that may come back out of order.
	return function(store, delay){
		return lang.delegate(store, {
			query: function(query, options){
				var queryResult = store.query(query, options);

				var totalDeferred = new Deferred();
				var resultsDeferred = new Deferred();
				resultsDeferred.total = totalDeferred;

				var resolveTotal = function(){
					totalDeferred.resolve(queryResult.total);
				};
				var resolveResults = function(){
					resultsDeferred.resolve(queryResult);
				};

				if(delay){
					setTimeout(resolveTotal, delay * (Math.random() + 0.5));
					setTimeout(resolveResults, delay * (Math.random() + 0.5));
				}
				else{
					resolveTotal();
					resolveResults();
				}
					
				return QueryResults(resultsDeferred);
			}
		});
	}
});