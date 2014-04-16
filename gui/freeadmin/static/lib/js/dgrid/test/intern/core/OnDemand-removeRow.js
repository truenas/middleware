define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/array",
	"dojo/_base/lang",
	"dojo/store/Memory",
	"dojo/store/Observable",
	"dojo/query",
	"dgrid/OnDemandList",
	"put-selector/put"
], function(test, assert, arrayUtil, lang, Memory, Observable, query, OnDemandList, put){

	test.suite("removeRow", function(){

		var list;

		function testInitialObservers(list, comment){
			var observers = list.observers;
			arrayUtil.forEach([true, true, true], function(test, i){
				assert.strictEqual(!!observers[i], test, [comment, "index is " + i + ", Expected is " + test]);
			});
		}

		function countObserverReferences(listId, observerIndex){
			var count = 0;
			query(".dgrid-row", listId).forEach(function(row){
				if(row.observerIndex === observerIndex){
					count += 1;
				}
			});
			return count;
		}

		test.beforeEach(function(){
			var data = [];
			for(var i = 0; i < 100; i++){
				data.push({id: i, value: i});
			}

			var store = Observable(new Memory({ data: data }));
			list = new OnDemandList({
				id: "list1",
				sort: "id",
				store: store,
				queryRowsOverlap: 2,
				renderRow: function(object){
					return put("div", object.value);
				},
				minRowsPerPage: 12,
				maxRowsPerPage: 12
			});
			put(document.body, list.domNode);
			put(list.domNode, "[style=height:300px]");
			list.startup();
		});

		test.afterEach(function(){
			list.destroy();
		});

		test.test("OnDemandList w/observers - remove 1 observer worth", function(){
			testInitialObservers(list, "Initial");
			for(var i = 0; i < 9; i++){
				var rowNode = document.getElementById("list1-row-" + i);
				assert.strictEqual(0, rowNode.observerIndex, "Row's observerIndex");
				list.removeRow(rowNode);
				testInitialObservers(list, "Iteration " + i);
			}

			list.removeRow(document.getElementById("list1-row-9"));
			assert.isFalse(!!list.observers[0], "First observer should not exist.");
			assert.isTrue(!!list.observers[1], "Second observer should exist.");
			assert.isTrue(!!list.observers[2], "Third observer should exist.");
		});

		test.test("OnDemandList w/observers and overlap - remove 2 observer worth", function(){
			testInitialObservers(list, "Initial");
			for(var i = 0; i < 20; i++){
				var rowNode = document.getElementById("list1-row-" + i);
				list.removeRow(rowNode);
			}
			assert.isFalse(!!list.observers[0], "First observer should not exist.");
			assert.isFalse(!!list.observers[1], "Second observer should not exist.");
			assert.isTrue(!!list.observers[2], "Third observer should exist.");
		});

		test.test("OnDemandList w/observers - remove all, clean up only", function(){
			testInitialObservers(list, "Initial");
			for(var i = 0; i < 9; i++){
				var rowNode = document.getElementById("list1-row-" + i);
				assert.strictEqual(0, rowNode.observerIndex, "Row's observerIndex");
				list.removeRow(rowNode, true);
				testInitialObservers(list, "Iteration " + i);
			}

			list.removeRow(document.getElementById("list1-row-9"), true);
			assert.isFalse(!!list.observers[0], "First observer should not exist.");
			assert.isTrue(!!list.observers[1], "Second observer should exist.");
			assert.isTrue(!!list.observers[2], "Third observer should exist.");
		});

		test.test("OnDemandList w/observers - remove last 2, clean up only", function(){
			// Removing the last two rows from observer #0 should not cancel the observer.
			testInitialObservers(list, "Initial");

			list.removeRow(document.getElementById("list1-row-7"), true);
			testInitialObservers(list, "Removed row 8");

			list.removeRow(document.getElementById("list1-row-8"), true);
			testInitialObservers(list, "Removed row 9");

			list.removeRow(document.getElementById("list1-row-1"), true);
			testInitialObservers(list, "Removed row 1");

			list.removeRow(document.getElementById("list1-row-0"), true);
			testInitialObservers(list, "Removed row 0");
		});
	});
});