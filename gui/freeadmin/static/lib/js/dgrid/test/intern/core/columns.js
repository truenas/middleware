define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/declare",
	"dojo/query",
	"dgrid/Grid",
	"dgrid/ColumnSet",
	"dgrid/test/data/base"
], function(test, assert, declare, query, Grid, ColumnSet){
	
	var grid;
	
	function runClassNameTests(){
		var domNode = grid.domNode,
			node;
		
		assert.strictEqual(query(".dgrid-cell.field-order", domNode).length, 10,
			"Each row (including header) should contain a cell with the field-order class");
		assert.strictEqual(query(".dgrid-cell.field-name", domNode).length, 10,
			"Each row (including header) should contain a cell with the field-name class");
		assert.strictEqual(query(".dgrid-cell.field-description", domNode).length, 10,
			"Each row (including header) should contain a cell with the field-description class");
		
		assert.strictEqual(query(".dgrid-cell.field-name.name-column.main-column", domNode).length, 10,
			"Each row's (including header's) field-name cell should also have the name-column and main-column classes");
		
		assert.strictEqual(query(".dgrid-cell.field-description.desc-row", domNode).length, 9,
			"Each body row's description cell should also have the desc-row class");
		node = query(".dgrid-header .dgrid-cell.field-description", domNode)[0];
		assert.strictEqual(node.className.indexOf("undefined"), -1,
			"Header row's description cell should NOT contain 'undefined' due to className returning ''");
		assert.isTrue(query(".dgrid-content .dgrid-cell.field-description", domNode).every(function(cell){
				return (/desc-\w+ desc-row/).test(cell.className);
			}),
			"Each body row's description cell has two desc-* classes (one being desc-row)");
	}
	
	test.suite("columns", function(){
		test.afterEach(function(){
			grid.destroy();
		});
		
		test.test("className property", function(){
			grid = new Grid({
				columns: {
					order: "Order",
					name: {
						label: "Name",
						className: "name-column main-column"
					},
					description: {
						label: "Description",
						className: function(object){
							return object ?
								"desc-" + object.name.replace(/ /g, "") + " desc-row" :
								"";
						}
					}
				}
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(testOrderedData);
			runClassNameTests();
		});
	});
	
	test.suite("columnSets", function(){
		test.afterEach(function(){
			grid.destroy();
		});
		
		test.test("className property", function(){
			grid = new (declare([Grid, ColumnSet]))({
				columnSets: [
					[[
						{ field: "order", label: "Order" },
						{
							field: "name",
							label: "Name",
							className: "name-column main-column"
						}
					]], [[
						{
							field: "description",
							label: "Description",
							className: function(object){
								return object ?
									"desc-" + object.name.replace(/ /g, "") + " desc-row" :
									"";
							}
						}
					]]
				]
			});
			document.body.appendChild(grid.domNode);
			grid.startup();
			grid.renderArray(testOrderedData);
			runClassNameTests();
		});
	});
});