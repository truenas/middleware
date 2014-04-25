define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/declare",
	"dojo/on",
	"dojo/query",
	"dijit/registry",
	"dijit/form/TextBox",
	"dgrid/Grid",
	"dgrid/OnDemandGrid",
	"dgrid/editor",
	"dgrid/test/data/base"
], function (test, assert, declare, on, query, registry, TextBox, Grid, OnDemandGrid, editor) {
	var grid;

	// testOrderedData: global from dgrid/test/data/base.js

	test.suite("editor column plugin", function () {

		test.afterEach(function () {
			if (grid) {
				grid.destroy();
			}
		});

		test.test("canEdit - always-on (instance-per-row) editor", function () {
			var results = {};
			var data = [
				{id: 1, data1: "Data 1.a", data2: "Data 2.a"},
				{id: 2, data1: "Data 1.b", data2: "Data 2.b"},
				{id: 3, data1: "Data 1.c", data2: "Data 2.c"}
			];
			grid = new Grid({
				columns: [
					{
						field: "data1",
						label: "Data 1"
					},
					editor({
						field: "data2",
						label: "Data 2",
						canEdit: function(object, value){
							results[object.id] = value;
						}
					})
				]
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(data);

			assert.strictEqual(results[1], "Data 2.a",
				"canEdit should have been called (item 1)");
			assert.strictEqual(results[2], "Data 2.b",
				"canEdit should have been called (item 2)");
			assert.strictEqual(results[3], "Data 2.c",
				"canEdit should have been called (item 3)");
		});


		test.test("canEdit - editOn (shared) editor", function () {
			var results = {};
			var data = [
				{id: 1, data1: "Data 1.a", data2: "Data 2.a"},
				{id: 2, data1: "Data 1.b", data2: "Data 2.b"},
				{id: 3, data1: "Data 1.c", data2: "Data 2.c"}
			];
			grid = new Grid({
				columns: [
					{
						field: "data1",
						label: "Data 1",
						id: "data1"
					},
					editor({
						field: "data2",
						label: "Data 2",
						id: "data2",
						canEdit: function(object, value){
							results[object.id] = value;
						}
					}, TextBox, "click")
				]
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(data);

			assert.isUndefined(results[1],
				"canEdit should not have been called yet for editOn editor (item 1)");
			assert.isUndefined(results[2],
				"canEdit should not have been called yet for editOn editor (item 2)");
			assert.isUndefined(results[3],
				"canEdit should not have been called yet for editOn editor (item 3)");

			grid.edit(grid.cell(1, "data2"));
			assert.isUndefined(results[1],
				"canEdit should not have been called yet for editOn editor (item 1)");
			assert.strictEqual(results[2], "Data 2.b",
				"canEdit should have been called for editOn editor (item 2)");
			assert.isUndefined(results[3],
				"canEdit should not have been called yet for editOn editor (item 3)");

			grid.edit(grid.cell(0, "data2"));
			assert.strictEqual(results[1], "Data 2.a",
				"canEdit should have been called for editOn editor (item 1)");
			assert.strictEqual(results[2], "Data 2.b",
				"canEdit should have been called for editOn editor (item 2)");
			assert.isUndefined(results[3],
				"canEdit should not have been called yet for editOn editor (item 3)");

			grid.edit(grid.cell(2, "data2"));
			assert.strictEqual(results[1], "Data 2.a",
				"canEdit should have been called for editOn editor (item 1)");
			assert.strictEqual(results[2], "Data 2.b",
				"canEdit should have been called for editOn editor (item 2)");
			assert.strictEqual(results[3], "Data 2.c",
				"canEdit should have been called for editOn editor (item 3)");
		});


		test.test("canEdit: suppress on false", function () {
			var rowIndex,
				cell,
				matchedNodes;

			function canEdit(data) {
				return data.order % 2;
			}
			
			grid = new OnDemandGrid({
				columns: {
					order: "step",
					name: editor({
						label: "Name",
						editor: "text",
						canEdit: canEdit
					}),
					description: editor({
						label: "Description",
						editor: "text",
						editOn: "click",
						canEdit: canEdit
					})
				}
			});

			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(testOrderedData);

			for (rowIndex = 0; rowIndex < testOrderedData.length; rowIndex++) {
				// Test always-on editors
				cell = grid.cell(rowIndex, "name");
				grid.edit(cell);
				matchedNodes = query("input", cell.element);

				if (canEdit(cell.row.data)) {
					assert.strictEqual(1, matchedNodes.length,
						"Cell with canEdit=>true should have an editor element");
				}
				else {
					assert.strictEqual(0, matchedNodes.length,
						"Cell with canEdit=>false should not have an editor element");
				}

				// Test non-always-on editors
				cell = grid.cell(rowIndex, "description");
				grid.edit(cell);
				matchedNodes = query("input", cell.element);

				if (canEdit(cell.row.data)) {
					assert.strictEqual(1, matchedNodes.length,
						"Cell with canEdit=>true should have an editor element");
				}
				else {
					assert.strictEqual(0, matchedNodes.length,
						"Cell with canEdit=>false should not have an editor element");
				}
			}
		});


		test.test("destroy editor widgets: native", function () {
			var matchedNodes;

			matchedNodes = query("input");
			assert.strictEqual(0, matchedNodes.length,
				"Before grid is created there should be 0 input elements on the page");

			grid = new OnDemandGrid({
				columns: {
					order: "step",
					name: editor({
						label: "Name",
						editor: "text"
					}),
					description: editor({
						label: "Description",
						editor: "text",
						editOn: "click"
					})
				}
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(testOrderedData);

			matchedNodes = query("input");
			assert.strictEqual(testOrderedData.length, matchedNodes.length,
				"There should be " + testOrderedData.length + " input elements for the grid's editors");

			grid.destroy();

			matchedNodes = query("input");
			assert.strictEqual(0, matchedNodes.length,
				"After grid is destroyed there should be 0 input elements on the page");
		});


		test.test("destroy editor widgets: Dijit", function () {
			assert.strictEqual(0, registry.length,
				"Before grid is created there should be 0 widgets on the page");

			grid = new OnDemandGrid({
				columns: {
					order: "step",
					name: editor({
						label: "Name",
						editor: TextBox
					}),
					description: editor({
						label: "Description",
						editor: TextBox,
						editOn: "click"
					})
				}
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(testOrderedData);

			// Expected is data length + 1 due to widget for editOn editor
			assert.strictEqual(testOrderedData.length + 1, registry.length,
				"There should be " + (testOrderedData.length + 1) + " widgets for the grid's editors");

			grid.destroy();

			assert.strictEqual(0, registry.length,
				"After grid is destroyed there should be 0 widgets on the page");
		});


		// Goal: test that when "grid.edit(cell)" is called the cell gets an editor with focus
		//
		// Observed behavior:
		// In a cell without an always-on editor, if you call "grid.edit(cell)"
		// repeatedly, the previously edited cell loses its content (not just its editor).
		// document.activeElement.blur() between calls of "grid.edit" does not
		// seem to work in this automated test, though it is of no consequence
		// since this test is simply testing the editor's presence, not its after-effects.
		//
		// grid.edit:
		//		In a cell with an always-on editor, the editor's "focus" event is fired and
		//		"document.activeElement" is set to the editor.
		//		In a cell with a click-to-activate editor, no "focus" event is fired and
		//		"document.activeElement" is the body.
		test.test("editor focus", function () {
			var rowIndex,
				cell,
				cellEditor;

			grid = new OnDemandGrid({
				columns: {
					order: "step",
					name: editor({
						label: "Name",
						editor: "text"
					}),
					description: editor({
						label: "Description",
						editor: "text",
						editOn: "click"
					})
				}
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(testOrderedData);

			for (rowIndex = 0; rowIndex < testOrderedData.length; rowIndex++) {
				// Calling 'grid.edit()' on different cells consecutively results in the last-edited
				// cell losing its content. It seems the blur process is important, so try to trigger that:
				document.activeElement.blur();

				// Test calling 'grid.edit()' in an always-on cell
				cell = grid.cell(rowIndex, "name");
				grid.edit(cell);

				cellEditor = query("input", cell.element)[0];
				assert.strictEqual(cellEditor, document.activeElement,
					"Editing a cell should make the cell's editor active");

				document.activeElement.blur();

				cell = grid.cell(rowIndex, "description");
				// Respond to the "dgrid-editor-show" event to ensure the
				// correct cell has an editor.  This event actually fires
				// synchronously, so we don't need to use this.async.
				on.once(grid.domNode, "dgrid-editor-show", function (event) {
					// document.activeElement is the body for some reason.
					// So at least check to ensure that the cell we called edit on
					// is the same as the cell passed to the "dgrid-editor-show" event.
					assert.strictEqual(cell.element, event.cell.element,
						"The activated cell should be being edited"
					);
				});

				grid.edit(cell);
			}
		});
	});
});
