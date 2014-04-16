define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/_base/declare",
	"dojo/dom-style",
	"dojo/dom-construct",
	"dojo/query",
	"dgrid/Grid",
	"dgrid/ColumnSet",
	"dgrid/extensions/ColumnHider",
	"dgrid/extensions/ColumnResizer",
	"dgrid/util/misc"
], function (test, assert, declare, domStyle, domConstruct, query,
		Grid, ColumnSet, ColumnHider, ColumnResizer, miscUtil) {

	test.suite("addCssRule", function(){
		var testDiv;
		
		// Setup / teardown
		test.before(function(){
			testDiv = domConstruct.create("div", null, document.body);
		});

		test.after(function(){
			domConstruct.destroy(testDiv);
		});

		// Tests
		test.test("addCssRule + remove", function(){
			testDiv.className = "foo";
			// cache original style and update .foo
			var origStyle = domStyle.getComputedStyle(testDiv).fontSize,
				rule = miscUtil.addCssRule(".foo", "font-size: 8px;");
			// check updated font size was applied
			assert.strictEqual("8px", domStyle.getComputedStyle(testDiv).fontSize,
				"Node with matching class has expected font-size");
			// remove the rule & make sure the computed style is good again
			rule.remove();
			assert.strictEqual(origStyle, domStyle.getComputedStyle(testDiv).fontSize,
				"Node with matching class no longer has font-size from removed rule");
			testDiv.className = "";
		});

		test.test("addCssRule get/set/remove", function(){
			testDiv.className = "bar";
			// cache original style and update .foo
			var origStyle = domStyle.getComputedStyle(testDiv).fontSize,
				rule = miscUtil.addCssRule(".bar", "font-size: 8px;");
			// check updated font size was applied
			assert.strictEqual("8px", rule.get("fontSize"),
				"rule.get('fontSize') reports expected value");
			// update the font size
			rule.set("fontSize", "9px");
			// verify that the size updated
			assert.strictEqual("9px", domStyle.getComputedStyle(testDiv).fontSize,
				"Node with matching class has expected font-size after set");
			// make sure rule.get works the same
			assert.strictEqual("9px", rule.get("fontSize"),
				"rule.get('fontSize') reports expected value after set");
			// remove the rule & make sure it updates
			rule.remove();
			assert.strictEqual(origStyle, domStyle.getComputedStyle(testDiv).fontSize,
				"Node with matching class no longer has font-size from removed rule");
			testDiv.className = "";
		});

		test.test("add/remove multiple rules in mixed order", function(){
			var origStyle = domStyle.getComputedStyle(testDiv).fontSize,
				rules = [],
				expected = { // hash containing test classes / values
					foo: "7px",
					bar: "8px",
					baz: "9px"
				},
				cls;
			
			function check(){
				// Test that all expected styles hold
				var cls;
				for(cls in expected){
					testDiv.className = cls;
					assert.strictEqual(expected[cls], domStyle.getComputedStyle(testDiv).fontSize,
						"Node with class " + cls + " has expected font-size");
				}
				testDiv.className = "";
			}
			
			// Create rules and maintain references to returned objects
			for(cls in expected){
				rules.push(miscUtil.addCssRule("." + cls, "font-size: " + expected[cls] + ";"));
			}
			
			// Do initial check, then remove rules one by one, out of order,
			// updating the hash and checking each time along the way
			check();
			
			rules[2].remove();
			expected.baz = origStyle;
			check();
			
			rules[0].remove();
			expected.foo = origStyle;
			check();
			
			rules[1].remove();
			expected.bar = origStyle;
			check();
		});

		test.test("addCssRule via dgrid APIs", function(){
			var values = ["7px", "8px"],
				origValues,
				grid;
			
			function createGrid(cleanAddedRules){
				grid = new Grid({
					id: "my.grid", // test escaping of CSS identifiers from methods
					columns: {
						name: "Name",
						value: "Value",
						comment: "Comment" // unstyled buffer
					},
					cleanAddedRules: cleanAddedRules
				});
				document.body.appendChild(grid.domNode);
				grid.startup();
			}
			
			function addRules(){
				var rules = [];
				
				rules.push(grid.addCssRule(".field-value", "font-size: " + values[0] + ";"));
				rules.push(grid.styleColumn("name", "font-size: " + values[1] + ";"));
				
				return rules;
			}
			
			function getStyles(){
				return [
					domStyle.getComputedStyle(query(".field-value", grid.domNode)[0]).fontSize,
					domStyle.getComputedStyle(query(".dgrid-column-name", grid.domNode)[0]).fontSize
				];
			}
			
			function checkRules(expected){
				var actual = getStyles(grid);
				assert.strictEqual(expected[0], actual[0],
					"Style modified via addCssRule has expected value");
				assert.strictEqual(expected[1], actual[1],
					"Style modified via styleColumn has expected value");
			}
			
			// Create grid for the first time
			createGrid(true);
			// Collect original style values for later cleanup check
			origValues = getStyles();
			// Add rules and make sure they applied as expected
			addRules();
			checkRules(values);
			// Destroy the grid, which should remove the style rules
			grid.destroy();
			
			// Create grid for the second time, with cleanAddedRules: false
			createGrid(false);
			// Before adding styles, make sure the ones from last time were removed
			checkRules(origValues);
			// Add rules and check again;
			// store the rules for tearDown since they won't be cleaned up
			this.rules = addRules();
			checkRules(values);
			// Destroy the grid, which should *not* remove the style rules
			grid.destroy();
			
			// Create grid for the third time
			createGrid(true);
			// Check that styles from last time still exist
			checkRules(values);
			// Destroy the grid (which won't remove the styles from last time,
			// since no handles were added to this exact instance)
			grid.destroy();
			// Clean up rule litter from cleanAddedRules: false test
			var i;
			for(i in this.rules){
				this.rules[i].remove();
			}
		});
	});

	test.suite("CSS escaping of IDs via dgrid APIs", function(){
	
		var grid;
		
		test.suite("Grid columns and columnsets", function(){
			function makeTest(func, id) {
				return function () {
					assert.doesNotThrow(function(){
						grid[func](id, "font-size: 8px;");
					}, null, func + " should escape special characters and not throw error");
					assert.strictEqual("8px", domStyle.getComputedStyle(query(".dgrid-cell")[0]).fontSize,
						"Column cell should have expected style");
				};
			}
			
			test.beforeEach(function(){
				grid = new (declare([Grid, ColumnSet]))({
					id: "i:d",
					columnSets: [[[
						{ field: "foo", id: "col:umn" }
					]]]
				});
				document.body.appendChild(grid.domNode);
				grid.startup();
			});
			
			test.afterEach(function(){
				grid.destroy();
			});
			
			test.test("styleColumn", makeTest("styleColumn", "col:umn"));
				
			// Currently ColumnSet IDs can't be customized so that isn't really an issue,
			// but this still tests escaping the grid ID
			test.test("styleColumnSet", makeTest("styleColumnSet", "0"));
		});
		
		test.suite("ColumnHider", function(){
			var ColumnHiderGrid = declare([Grid, ColumnHider]);
			
			test.afterEach(function(){
				grid.destroy();
			});
			
			test.test("Hiding column after construction", function(){
				assert.doesNotThrow(function(){
					grid = new ColumnHiderGrid({
						id: "i:d",
						columns: [
							{ field: "foo", id: "col:umn" }
						]
					});
				}, null, "ColumnHider should not throw error during construction");
				document.body.appendChild(grid.domNode);
				grid.startup();
				
				assert.doesNotThrow(function(){
					grid._hideColumn("col:umn");
				}, null, "_hideColumn should escape special characters and not throw error");
				assert.strictEqual(query(".dgrid-cell")[0].offsetHeight, 0,
					"Column should be hidden");
			});
			
			test.test("Hiding column during construction", function(){
				assert.doesNotThrow(function(){
					grid = new ColumnHiderGrid({
						id: "i:d",
						columns: [
							{ field: "foo", id: "col:umn", hidden: true }
						]
					});
				}, null, "ColumnHider should not throw error during construction");
				document.body.appendChild(grid.domNode);
				grid.startup();
				assert.strictEqual(query(".dgrid-cell")[0].offsetHeight, 0,
					"Column should be hidden");
			});
		});
		
		test.suite("ColumnResizer", function(){
			var ColumnResizerGrid = declare([Grid, ColumnResizer]);
			
			test.afterEach(function(){
				grid.destroy();
			});
			
			test.test("Resizing column after construction", function(){
				assert.doesNotThrow(function(){
					grid = new ColumnResizerGrid({
						id: "i:d",
						columns: [
							{ field: "foo", id: "col:umn" },
							{ field: "bar" }
						]
					});
				}, null, "ColumnResizer should not throw error during construction");
				document.body.appendChild(grid.domNode);
				grid.startup();
				
				assert.doesNotThrow(function(){
					grid.resizeColumnWidth("col:umn", 100);
				}, null, "resizeColumnWidth should escape special characters and not throw error");
				assert.strictEqual(query(".dgrid-cell-padding")[0].offsetWidth, 100,
					"Column should be the expected width");
			});
			
			test.test("Resizing column during construction", function(){
				assert.doesNotThrow(function(){
					grid = new ColumnResizerGrid({
						id: "i:d",
						columns: [
							{ field: "foo", id: "col:umn", width: 100 },
							{ field: "bar" }
						]
					});
				}, null, "ColumnResizer should not throw error during construction");
				document.body.appendChild(grid.domNode);
				grid.startup();
				assert.strictEqual(query(".dgrid-cell-padding")[0].offsetWidth, 100,
					"Column should be the expected width");
			});
		});
	});
});