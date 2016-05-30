define([
	'dojo/_base/declare',
	'dojo/Deferred',
	'./QueryResults',
	'dojo/when'
], function (declare, Deferred, QueryResults, when) {
	// module:
	//		this is a mixin that can be used to provide async methods,
	// 		by implementing their sync counterparts
	function promised(method, query) {
		return function() {
			var deferred = new Deferred();
			try {
				deferred.resolve(this[method].apply(this, arguments));
			} catch (error) {
				deferred.reject(error);
			}
			if (query) {
				// need to create a QueryResults and ensure the totalLength is
				// a promise.
				var queryResults = new QueryResults(deferred.promise);
				queryResults.totalLength = when(queryResults.totalLength);
				return queryResults;
			}
			return deferred.promise;
		};
	}
	return declare(null, {
		get: promised('getSync'),
		put: promised('putSync'),
		add: promised('addSync'),
		remove: promised('removeSync'),
		fetch: promised('fetchSync', true),
		fetchRange: promised('fetchRangeSync', true)
	});
});
