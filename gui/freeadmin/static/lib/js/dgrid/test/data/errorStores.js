define([
	"dojo/_base/lang",
	"dojo/_base/Deferred",
	"dojo/store/Memory",
	"dojo/store/util/QueryResults",
	"./base"
], function(lang, Deferred, Memory, QueryResults){
	// summary:
	//		Returns a hash containing stores which generate errors on specific
	//		methods, synchronously or asynchronously.
	
	var queryStore = new Memory(),
		asyncQueryStore = new Memory(),
		putStore = new Memory({ data: lang.clone(testTypesStore.data) }),
		asyncPutStore = new Memory({ data: lang.clone(testTypesStore.data) });
	
	queryStore.query = function() {
		throw new Error("Error on sync query");
	};
	
	putStore.put = function() {
		throw new Error("Error on sync put");
	};
	
	asyncQueryStore.query = function() {
		var dfd = new Deferred();
		setTimeout(function() { dfd.reject("Error on async query"); }, 200);
		
		var results = new QueryResults(dfd.promise);
		results.total = 0;
		return results;
	};
	
	asyncPutStore.put = function() {
		var dfd = new Deferred();
		setTimeout(function() { dfd.reject("Error on async put"); }, 200);
		return dfd.promise;
	};
	
	return {
		query: queryStore,
		put: putStore,
		asyncQuery: asyncQueryStore,
		asyncPut: asyncPutStore
	};
})