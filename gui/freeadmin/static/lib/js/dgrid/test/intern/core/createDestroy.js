define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/declare",
	"dgrid/List",
	"dgrid/TouchScroll",
	"dijit/registry",
	"dijit/form/TextBox",
	"dgrid/test/data/base"
], function (test, assert, declare, List, TouchScroll, registry, TextBox) {
	
	test.suite("createDestroy", function(){
		test.test("no params list", function(){
			var list = new List();
			document.body.appendChild(list.domNode);
			list.startup();
			list.renderArray([ "foo", "bar", "baz" ]);
			
			assert.strictEqual(list.contentNode.children.length, 3, 
				"List's contentNode has expected number of children after renderArray");
			
			list.destroy();
			assert.notStrictEqual(document.body, list.parentNode,
				"List is removed from body after destroy");
		});
		
		test.test("TouchScroll with useTouchScroll: false", function(){
			// Ensure TouchScroll is inherited for this test
			var list = new (declare([TouchScroll, List]))({ useTouchScroll: false });
			
			// This should not cause an error
			assert.doesNotThrow(function(){
				list.destroy();
			}, null, 'destroy should not throw error');
		});
	});
});