define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/declare",
	"dojo/on",
	"dgrid/Grid",
	"dgrid/OnDemandGrid",
	"dgrid/extensions/Pagination",
	"dgrid/test/data/errorStores",
	"dgrid/test/data/base"
], function (test, assert, declare, on, Grid, OnDemandGrid, Pagination, errorStores) {
	
	var PaginationGrid = declare([Grid, Pagination]),
		grid;

	// Common reusable function for tests
	function storeTest(CustomGrid, store, expectSuccess, dfd){
		var expectedEvent = expectSuccess ? "dgrid-refresh-complete" : "dgrid-error",
			unexpectedEvent = !expectSuccess ? "dgrid-refresh-complete" : "dgrid-error";
			grid = new CustomGrid({
				sort: "id",
				store: store
			});
		
		// Hook up event handler before calling startup, to be able to
		// test both synchronous and asynchronous stores
		on.once(grid, expectedEvent, function(){
			// After receiving the expected event, perform a refresh,
			// to also test resolution/rejection of the promise it returns.
			grid.refresh().then(function(){
				dfd[expectSuccess ? "resolve" : "reject"]();
			}, function(){
				dfd[!expectSuccess ? "resolve" : "reject"]();
			});
		});
		
		// Also hook up the opposite event handler, to signal failure
		on.once(grid, unexpectedEvent, function(){
			dfd.reject(new Error("Expected " + expectedEvent + " to fire, but " +
				unexpectedEvent + " fired instead."));
		});

		document.body.appendChild(grid.domNode);
		grid.startup();
		return dfd;
	}

	test.suite("stores", function(){
		// Setup / teardown
		test.afterEach(function(){
			grid.destroy();
		});

		// Tests
		test.test("OnDemandGrid + sync store", function(){
			storeTest(OnDemandGrid, testStore, true, this.async());
		});

		test.test("OnDemandGrid + async store", function(){
			storeTest(OnDemandGrid, testAsyncStore, true, this.async());
		});

		test.test("OnDemandGrid + sync store w/ error", function(){
			storeTest(OnDemandGrid, errorStores.query, false, this.async());
		});

		test.test("OnDemandGrid + async store w/ error", function(){
			storeTest(OnDemandGrid, errorStores.asyncQuery, false, this.async());
		});

		test.test("PaginationGrid + sync store", function(){
			storeTest(PaginationGrid, testStore, true, this.async());
		});

		test.test("PaginationGrid + async store", function(){
			storeTest(PaginationGrid, testAsyncStore, true, this.async());
		});

		test.test("PaginationGrid + sync store w/ error", function(){
			storeTest(PaginationGrid, errorStores.query, false, this.async());
		});

		test.test("PaginationGrid + async store w/ error", function(){
			storeTest(PaginationGrid, errorStores.asyncQuery, false, this.async());
		});
	});
});