define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/declare",
	"dojo/dom-class",
	"dojo/query",
	"dojo/store/Memory",
	"dojo/store/Observable",
	"dgrid/OnDemandList",
	"put-selector/put"
], function(test, assert, declare, domClass, query, Memory, Observable, OnDemandList, put){

	var widget,
		storeCounter = 0;

	function destroyWidget(){
		if(widget){
			widget.destroy();
			widget = null;
		}
	}

	function indexToId(index){
		return (index + 1) * 10;
	}

	function createItem(index){
		var id = indexToId(index);
		return {id: id, value: "Value " + id + " / Store " + storeCounter};
	}

	function createData(numStoreItems){
		var data = [];
		for(var i = 0; i < numStoreItems; i++){
			data.push(createItem(i));
		}
		return data;
	}

	function createStore(numStoreItems){
		storeCounter++;
		return Observable(new Memory({
			data: createData(numStoreItems)
		}));
	}

	function createList(numStoreItems, itemsPerQuery, overlap){
		widget = new OnDemandList({
			store: createStore(numStoreItems),
			minRowsPerPage: itemsPerQuery,
			maxRowsPerPage: itemsPerQuery,
			queryRowsOverlap: overlap,
			renderRow: function(object){
				return put("div", object.value);
			},
			sort: "id"
		});
		document.body.appendChild(widget.domNode);
		widget.startup();
	}

	function itemTest(itemAction, index, numToModify, backwards){
		// Creates a single test case for performing an action on numToModify rows/items.
		var description = itemAction.actionName + " " + numToModify + " item" + (numToModify > 1 ? "s" : "") +
			" starting at index " + index + ", in " + (backwards ? "decreasing" : "increasing") + " order";

		numToModify = numToModify || 1;

		test.test(description, function(){
			var i,
				cnt,
				step = function(){
					cnt++;
					backwards ? i-- : i++;
				},
				tmp,
				expectedValues = [],
				msgPrefix;

			function testRow(element, i){
				var expectedValue = expectedValues[i];
				if(expectedValue == null || expectedValue.deleted){
					assert.isTrue(element == null, msgPrefix + "row at index " + i + " should not be found");
				}else{
					expectedValue = expectedValue.value;
					assert.isTrue(element != null, msgPrefix + "row at index " + i + " with an expected value of \"" + expectedValue + "\" is missing");
					assert.strictEqual(expectedValue, element.innerHTML, msgPrefix + element.innerHTML + " should be " + expectedValue);
				}
			}

			// Perform the actions and update the array of expected values.
			expectedValues = createData(widget.store.data.length);
			for(i = index, cnt = 0; cnt < numToModify; step()){
				itemAction(indexToId(i), expectedValues);
			}

			// Use the dgrid widget API to test if the action was performed properly.
			msgPrefix = "dgrid API: ";
			tmp = [];
			for(i = 0; i < expectedValues.length; i++){
				var expectedValue = expectedValues[i],
					expectedId = expectedValue.id;
				testRow(widget.row(expectedId).element, i);
				if(!expectedValue.deleted){
					tmp.push(expectedValue);
				}
			}
			expectedValues = tmp;

			// Query the DOM to verify the structure matches the expected results.
			msgPrefix = "DOM query: ";
			query(".dgrid-row", widget.domNode).forEach(testRow);
		});
	}

	function itemTestSuite(widgetClassName, storeSize, itemsPerQuery, overlap, config){
		// Create a test suite that performs one action type (itemAction) on 1 to config.itemsModifiedMax with
		// a given amount of overlap.
		var index, numToModify;

		test.suite(widgetClassName + " with " + overlap + " overlap", function(){

			test.beforeEach(function(){
				createList(storeSize, itemsPerQuery, overlap);
			});

			test.afterEach(destroyWidget);

			// Modify items counting up.
			for(numToModify = 1; numToModify <= config.itemsModifiedMax; numToModify++){
				for(index = 0; index <= (storeSize - numToModify); index++){
					itemTest(config.itemAction, index, numToModify);
				}
			}
			// Modify items counting down.  Starting at a count of 2 because
			// single item modification were tested above.
			for(numToModify = 2; numToModify <= config.itemsModifiedMax; numToModify++){
				for(index = numToModify - 1; index < storeSize; index++){
					itemTest(config.itemAction, index, numToModify, true);
				}
			}
		});
	}

	function itemActionTestSuite(description, itemAction, config){
		// Creates multiple item test suites for a given action (itemAction):
		// - a list that executes a single query
		// - lists with overlap from 0 to config.itemOverlapMax

		// Note: for debugging, comment out the contents of destroyWidget so the dgrid widgets are not destroyed.
		// Each widget uses a different store id and those ids are used in the row contents allowing you to
		// easily match up an error message like
		//  "Error: dgrid API: row at index 2 with an expected value of "Value 30 / Store 10 / Changed!" is missing"
		// with the correct widget on the page.
		config.itemAction = itemAction;

		test.suite(description, function(){
			// Test widgets with only one query: total item count equals item count per query.
			itemTestSuite("OnDemandList one query", config.itemsPerQuery, config.itemsPerQuery, 0, config);

			// Test widgets that make multiple query requests: twice as many items as items per query so multiple
			// queries will create multiple observers.
			var storeSize = config.itemsPerQuery * 2;
			// Test with OnDemandList with varying overlap values
			for(var overlap = 0; overlap <= config.itemOverlapMax; overlap++){
				itemTestSuite("OnDemandList multiple queries", storeSize, config.itemsPerQuery, overlap, config);
			}
		});
	}

	function itemAddEmptyStoreTest(itemsToAddCount, itemsPerQuery, overlap){
		var i;

		function rowHasClass(rowNode, cssClass){
			assert.isTrue(domClass.contains(rowNode, cssClass), rowNode.outerHTML + " should have " + cssClass);
		}

		test.test("Add " + itemsToAddCount + " items with " + overlap + " overlap", function(){
			createList(0, itemsPerQuery, overlap);
			var store = widget.store;
			for(i = 0; i < itemsToAddCount; i++){
				store.put(createItem(i));
			}

			var rows = query(".dgrid-content > div", widget.domNode);
			rowHasClass(rows[0], "dgrid-preload");
			for(i = 1; i <= itemsToAddCount; i++){
				rowHasClass(rows[i], (i % 2) ? "dgrid-row-even" : "dgrid-row-odd");
			}
			rowHasClass(rows[i], "dgrid-preload");

			for(i = 0; i < itemsToAddCount; i++){
				store.put(createItem(i));
			}

			rows = query(".dgrid-content > div", widget.domNode);
			rowHasClass(rows[0], "dgrid-preload");
			for(i = 1; i <= itemsToAddCount; i++){
				rowHasClass(rows[i], (i % 2) ? "dgrid-row-even" : "dgrid-row-odd");
			}
			rowHasClass(rows[i], "dgrid-preload");
		});
	}

	function itemAddEmptyStoreTestSuite(config){
		test.suite("Add items to empty store", function(){

			test.afterEach(destroyWidget);

			itemAddEmptyStoreTest(1, config.itemsPerQuery, 0);

			// Test with OnDemandList with varying overlap values
			for(var overlap = 0; overlap <= config.itemOverlapMax; overlap++){
				itemAddEmptyStoreTest(config.itemsPerQuery + overlap + 1, config.itemsPerQuery, overlap);
			}
		});
	}

	test.suite("observable lists", function(){
		// Creates test suites that execute the following actions on OnDemandLists with varying amount of
		// overlap and modifying varying number of items:
		// - modify existing items
		// - remove existing items
		// - add new items before existing items
		// - add new items after existing items

		function findIndex(id, objs){
			for(var i = 0; i < objs.length; i++){
				var obj = objs[i];
				if(obj && obj.id === id){
					return i;
				}
			}
			return -1;
		}

		var modifyAction = function(id, expectedValues){
			var index = findIndex(id, expectedValues);
			var value = expectedValues[index].value + " / Changed!";
			var dataObj = {id: id, value: value};
			widget.store.put(dataObj);
			expectedValues[index] = dataObj;
		};
		modifyAction.actionName = "Modify";

		var removeAction = function(id, expectedValues){
			widget.store.remove(id);
			var index = findIndex(id, expectedValues);
			expectedValues[index].deleted = true;
		};
		removeAction.actionName = "Remove";

		var addBeforeAction = function(id, expectedValues){
			var index = findIndex(id, expectedValues);
			var obj = {id: id - 5, value: expectedValues[index].value + " / Added before!"};
			widget.store.add(obj);
			expectedValues.splice(index, 0, obj);
		};
		addBeforeAction.actionName = "Add before";

		var addAfterAction = function(id, expectedValues){
			var index = findIndex(id, expectedValues);
			var obj = {id: id + 5, value: expectedValues[index].value + " / Added after!"};
			widget.store.add(obj);
			expectedValues.splice(index + 1, 0, obj);
		};
		addAfterAction.actionName = "Add after";

		// Run a test case with each action (modify, remove, add before, add after) and vary the amount of
		// queryRowsOverlap and vary the number of items modified during each test case.  A configuration
		// object controls the amount of variation.  The properties are:
		// itemsPerQuery - The OnDemandList is configured to request this number of items per query.
		//		This property also determines the size of the store.  Test cases run with a store size
		//		equal to this number and test cases run with a store size twice this number.
		// itemOverlapMax - Each test case is executed with a queryRowsOverap value of 0 up to this number.
		// itemsModifiedMax - Each test is executed where the number of items modified, deleted or added is
		//		1 up to this number; all of the test cases are run where 1 item is modified and then again
		//		with 2 items being modified and so on.
		var config = {
			itemsPerQuery: 3,
			itemOverlapMax: 2,
			itemsModifiedMax: 2
		};
		itemActionTestSuite("Modify store items", modifyAction, config);
		itemActionTestSuite("Remove store items", removeAction, config);
		itemActionTestSuite("Insert store items before", addBeforeAction, config);
		itemActionTestSuite("Insert store items after", addAfterAction, config);

		itemAddEmptyStoreTestSuite(config);
	});
});