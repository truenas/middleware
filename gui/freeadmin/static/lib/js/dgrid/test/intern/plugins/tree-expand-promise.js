define([
	"intern!tdd",
	"intern/chai!assert",
	"dgrid/Grid",
	"dgrid/OnDemandGrid",
	"dgrid/_StoreMixin",
	"dgrid/tree",
	"dojo/_base/declare",
	"dojo/_base/lang",
	"dojo/_base/Deferred",
	"dojo/on",
	"dojo/store/Memory",
	"dojo/store/util/QueryResults",
	"dojo/query"
], function(test, assert, Grid, OnDemandGrid, _StoreMixin, tree, declare, lang, Deferred, on,
		Memory, QueryResults, query){

	test.suite("tree (expand + promise)", function(){
		var grid,
			TreeStore = declare(Memory, {
				// A memory store with methods to support a tree
				getChildren: function(parent, options){
					// Support persisting the original query via options.originalQuery
					// so that child levels will filter the same way as the root level
					return this.query(
						lang.mixin({}, options && options.originalQuery || null,
							{ parent: parent.id }),
						options);
				},
				mayHaveChildren: function(){
					return true;
				},
				query: function(query, options){
					query = query || {};
					options = options || {};

					if(!query.parent && !options.deep){
						// Default to a single-level query for root items (no parent)
						query.parent = undefined;
					}
					return this.queryEngine(query, options)(this.data);
				}
			}),
			AsyncTreeStore = declare(TreeStore, {
				// TreeStore with an asynchronous query method.
				query: function(){
					this.dfd = new Deferred();
					this.queryResults = this.inherited(arguments);
					var promise = this.dfd.promise,
						results = new QueryResults(promise);
					results.total = this.queryResults.total;
					return results;
				},
				resolve: function(){
					// Allows the test to control when the store query is resolved.
					this.dfd.resolve(this.queryResults);
				},
				reject: function(error){
					// Allows the test to control when the store query is rejected.
					this.dfd.reject(error);
				}
			}),
			StoreMixinGrid = declare([Grid, _StoreMixin]),
			syncStore = new TreeStore({ data: createData() }),
			asyncStore = new AsyncTreeStore({ data: createData() });

		function createData(){
			return [
				{ id: 1, node: "Node 1", value: "Value 1"},
				{ id: 2, node: "Node 2", value: "Value 2", parent: 1},
				{ id: 3, node: "Node 3", value: "Value 3", parent: 2},
				{ id: 4, node: "Node 4", value: "Value 4", parent: 2},
				{ id: 5, node: "Node 5", value: "Value 5"}
			];
		}

		function createGrid(store){
			grid = new OnDemandGrid({
				store: store,
				columns: [
					tree({field: "node", label: "Node"}),
					{field: "value", label: "Value"}
				]
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
		}

		function createNoRenderQueryGrid(store){
			grid = new StoreMixinGrid({
				store: store,
				columns: [
					tree({field: "node", label: "Node"}),
					{field: "value", label: "Value"}
				]
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(grid.store.query());
		}

		function destroyGrid(){
			if(grid){
				grid.destroy();
				grid = null;
			}
		}

		function createOnPromise(target, event) {
			// Creates a promise based on an on.once call.
			// Resolves to the event passed to the handler function.
			var dfd = new Deferred(function () {
					handle.remove();
				}),
				handle = on.once(target, event, function (event) {
					dfd.resolve(event);
				});

			return dfd.promise;
		}

		function delayedResolve() {
			setTimeout(function(){ grid.store.resolve(); }, 10);
		}

		test.suite("tree + sync store", function(){
			test.beforeEach(function(){
				createGrid(syncStore);
			});
			test.afterEach(destroyGrid);

			// Tests
			test.test("expand + no callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				grid.expand(1);
				assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
			});

			test.test("expand + callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				return grid.expand(1).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
				});
			});

			test.test("expand + multiple callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				return grid.expand(1).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
					return grid.expand(2);
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length, "Grid should have 5 rows");
					return grid.expand(4);
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length, "Grid should have 5 rows");
				});
			});

			test.test("duplicate expand + callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				return grid.expand(1).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
					return grid.expand(1);
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows (no query)");
				});
			});
		});

		test.suite("tree + async store", function(){
			test.beforeEach(function(){
				createGrid(asyncStore);
			});
			test.afterEach(destroyGrid);

			test.test("expand + callback", function(){
				var promise = createOnPromise(grid, "dgrid-refresh-complete").then(function(){
					// Start testing when the grid is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows before expand resolves");
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should have 3 rows");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});

			test.test("expand + multiple callback", function(){
				var promise = createOnPromise(grid, "dgrid-refresh-complete").then(function(){
					// Start testing when the grid is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows before expand resolves");
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should have 3 rows");
					var promise = grid.expand(2);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 3 rows before expand resolves");
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length,
						"Grid should have 5 rows");
					var promise = grid.expand(4);
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 5 rows after expanding item with no children");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});

			test.test("duplicate expand + callback", function(){
				var promise = createOnPromise(grid, "dgrid-refresh-complete").then(function(){
					// Start testing when the grid is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should have 3 rows");
					return grid.expand(1);
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 3 rows (no query)");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});

			test.test("expand + callback, rejecting", function(){
				var errorCount = 0;

				grid.on("dgrid-error", function(event){
					event.preventDefault(); // Suppress log message
					errorCount++;
				});

				var promise = createOnPromise(grid, "dgrid-refresh-complete").then(function(){
					// Start testing when the grid is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows before expand resolves");
					setTimeout(function(){ grid.store.reject("Rejected"); }, 10);
					return promise;
				}).then(function () {
					throw new Error('Promise should have been rejected');
				}, function(){
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows after rejected promise");
					assert.strictEqual(1, errorCount,
						"The grid should have emitted a single error event");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});
		});

		test.suite("tree + no renderQuery + sync store", function(){
			test.beforeEach(function(){
				createNoRenderQueryGrid(syncStore);
			});
			test.afterEach(destroyGrid);

			test.test("expand + callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				grid.expand(1);
				assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
			});

			test.test("expand + callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				return grid.expand(1).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
				});
			});

			test.test("expand + multiple callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				return grid.expand(1).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
					return grid.expand(2);
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length, "Grid should have 5 rows");
					return grid.expand(4);
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length, "Grid should have 5 rows");
				});
			});

			test.test("duplicate expand + callback", function(){
				assert.strictEqual(2, query(".dgrid-row", grid.domNode).length, "Grid should have 2 rows");
				return grid.expand(1).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows");
					return grid.expand(1);
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length, "Grid should have 3 rows (no query)");
				});
			});
		});

		test.suite("tree + no renderQuery + async store", function(){
			test.beforeEach(function(){
				createNoRenderQueryGrid(asyncStore);
			});

			test.afterEach(destroyGrid);

			test.test("expand + callback", function(){
				var promise = grid.store.dfd.then(function(){
					// Start testing when the initial query is done is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows before expand resolves");
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should have 3 rows");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});

			test.test("expand + multiple callback", function(){
				var promise = grid.store.dfd.then(function(){
					// Start testing when the initial query is done is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows before expand resolves");
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should have 3 rows");
					var promise = grid.expand(2);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 3 rows before expand resolves");
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length,
						"Grid should have 5 rows");
					var promise = grid.expand(4);
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(5, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 5 rows after expanding item with no children");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});

			test.test("duplicate expand + callback", function(){
				var promise = grid.store.dfd.then(function(){
					// Start testing when the initial query is done is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);
					delayedResolve();
					return promise;
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should have 3 rows");
					return grid.expand(1);
				}).then(function(){
					assert.strictEqual(3, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 3 rows (no query)");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});

			test.test("expand + callback, rejecting", function(){
				var promise = grid.store.dfd.then(function(){
					// Start testing when the initial query is done is ready.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should have 2 rows");
					var promise = grid.expand(1);

					// Verify that the result is the same before the query resolves.
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows before expand resolves");
					setTimeout(function(){ grid.store.reject("Rejected"); }, 10);
					return promise;
				}).then(function(){
					throw new Error('Promise should have been rejected');
				}, function(){
					assert.strictEqual(2, query(".dgrid-row", grid.domNode).length,
						"Grid should still have 2 rows after rejected promise");
				});

				assert.strictEqual(0, query(".dgrid-row", grid.domNode).length,
					"Grid should have 0 rows before first async query resolves");
				// Resolve the grid's initial store query.
				delayedResolve();
				return promise;
			});
		});
	});
});