define([
	"intern!tdd",
	"intern/chai!assert",
	"dgrid/List",
	"dgrid/Grid",
	"dgrid/editor",
	"dijit/registry",
	"dijit/form/TextBox",
	"dgrid/test/data/base"
], function (test, assert, List, Grid, editor, registry, TextBox) {
	
	test.suite("createDestroy", function(){
		// Tests
		test.test("no params list", function(){
			// build a list, start it up, and render
			var list = new List();
			document.body.appendChild(list.domNode);
			list.startup();
			list.renderArray([ "foo", "bar", "baz" ]);

			// check number of children
			assert.strictEqual(list.contentNode.children.length, 3, 
				"List's contentNode has expected number of children after renderArray");

			// kill it & make sure we are all cleaned up
			list.destroy();
			assert.notStrictEqual(document.body, list.parentNode,
				"List is removed from body after destroy");
		});

		test.test("editor grid", function(){
			// make sure the registry is initially empty
			assert.strictEqual(0, registry.length,
				"dijit registry should have no entries before creating grid");

			// build a grid with editors, place it, and render
			var grid = new Grid({
				columns: {
					order: "step",
					name: editor({}, TextBox, "dblclick"),
					description: editor({ label: "what to do", sortable: false }, TextBox)
				}
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(testOrderedData);

			// check the registry
			assert.strictEqual(testOrderedData.length + 1, registry.length,
				"dijit registry has 1 entry per row plus 1 shared editor widget");

			// kill and check the registry again
			grid.destroy();
			assert.strictEqual(0, registry.length,
				"dijit registry has 0 entries after destroy");
		});
	});
});