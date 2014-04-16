define([
	"intern!tdd",
	"intern/chai!assert",
	"../../../OnDemandGrid",
	"dgrid/tree",
	"dgrid/util/has-css3",
	"dgrid/util/misc",
	"dojo/_base/lang",
	"dojo/_base/Deferred",
	"dojo/on",
	"dojo/store/Memory",
	"dojo/store/Observable",
	"put-selector/put"
], function(test, assert, OnDemandGrid, tree, has, miscUtil, lang, Deferred, on, Memory, Observable, put){

	var grid,
		testDelay = 15,
		hasTransitionEnd = has("transitionend");

	function createGrid(){
		var data = [],
			store,
			i,
			k;

		for(i = 0; i < 5; i++){
			var parentId = "" + i;
			data.push({
				id: parentId,
				value: "Root " + i
			});
			for(k = 0; k < 100; k++){
				data.push({
					id: i + ":" + k,
					parentId: parentId,
					value: "Child " + k
				});
			}
		}

		store = new Observable(new Memory({
			data: data,
			getChildren: function(parent, options){
				return this.query(
					lang.mixin({}, options.originalQuery || null, { parentId: parent.id }), options);
			},
			mayHaveChildren: function(parent){
				return parent.parentId == null;
			},
			query: function(query, options){
				query = query || {};
				options = options || {};

				if(!query.parentId && !options.deep){
					query.parentId = undefined;
				}
				return this.queryEngine(query, options)(this.data);
			}
		}));

		grid = new OnDemandGrid({
			sort: "id",
			store: store,
			columns: [
				tree({ label: "id", field: "id" }),
				{ label: "value", field: "value"}
			]
		});
		put(document.body, grid.domNode);
		grid.startup();
	}

	function destroyGrid(){
		grid.destroy();
		grid = null;
	}

	function testRowExists(dataItemId, exists){
		// Tests existence of a row for a given item ID;
		// if `exists` is false, tests for nonexistence instead
		exists = exists !== false;
		assert[exists ? "isNotNull" : "isNull"](document.getElementById(grid.id + "-row-" + dataItemId),
				"A row for " + dataItemId + " should " + (exists ? "" : "not ") + "exist in the grid.");
	}

	function wait(delay){
		// Returns a promise resolving after the given number of ms (or testDelay by default)
		var dfd = new Deferred();
		setTimeout(function(){
			dfd.resolve();
		}, delay || testDelay);
		return dfd.promise;
	}

	// Define a function returning a promise resolving once children are expanded.
	// On browsers which support CSS3 transitions, this occurs when transitionend fires;
	// otherwise it occurs immediately.
	var expand = hasTransitionEnd ? function(id){
		var dfd = new Deferred();

		on.once(grid, hasTransitionEnd, function(){
			dfd.resolve();
		});

		grid.expand(id);
		return dfd.promise;
	} : function(id){
		var dfd = new Deferred();
		grid.expand(id);
		dfd.resolve();
		return dfd.promise;
	};

	function scrollToEnd(){
		var dfd = new Deferred(),
			handle;

		handle = on.once(grid.bodyNode, "scroll", miscUtil.debounce(function(){
			dfd.resolve();
		}));

		grid.scrollTo({ y: grid.bodyNode.scrollHeight });

		return dfd.promise;
	}

	test.suite("tree", function(){
		test.suite("large family expansion", function(){

			test.beforeEach(function(){
				createGrid();

				// Firefox in particular seems to skip transitions sometimes
				// if we don't wait a bit after creating and placing the grid
				return wait();
			});

			test.afterEach(destroyGrid);

			test.test("expand first row", function(){
				return expand(0)
					.then(function(){
						testRowExists("0:0");
						testRowExists("0:99", false);
					});
			});

			test.test("expand first row + scroll to bottom", function(){
				return expand(0)
					.then(scrollToEnd)
					.then(function(){
						testRowExists("0:0");
						testRowExists("0:99");
					});
			});

			test.test("expand last row", function(){
				return expand(4).then(function(){
					testRowExists("4:0");
					testRowExists("4:99", false);
				});
			});

			test.test("expand last row + scroll to bottom", function(){
				return expand(4)
					.then(scrollToEnd)
					.then(function(){
						testRowExists("4:0");
						testRowExists("4:99");
					});
			});

			test.test("expand first and last rows + scroll to bottom", function(){
				return expand(0)
					.then(scrollToEnd)
					.then(function(){
						return expand(4);
					})
					.then(scrollToEnd)
					.then(function(){
						testRowExists("4:0");
						testRowExists("4:99");
					});
			});

			test.test("expand hidden", function() {
				var dfd = this.async(1000);

				grid.domNode.style.display = "none";
				grid.expand(0);
				grid.domNode.style.display = "block";

				// Since the grid is not displayed the expansion will occur without a transitionend event
				// However, DOM updates from the expand will not complete within the current stack frame
				setTimeout(dfd.callback(function() {
					var connected = grid.row(0).element.connected;
					assert.isTrue(connected && connected.offsetHeight > 0,
						"Node should be expanded with non-zero height");
				}), 0);
			});
		});

		test.suite("tree + observable", function(){
			test.beforeEach(createGrid);
			test.afterEach(destroyGrid);

			test.test("child modification", function(){
				return expand(0).then(function(){
					testRowExists("0:0");
					assert.doesNotThrow(function(){
						grid.store.put({
							id: "0:0",
							value: "Modified",
							parentId: "0"
						});
					}, null, 'Modification of child should not throw error');
				});
			});
		});
	});
});