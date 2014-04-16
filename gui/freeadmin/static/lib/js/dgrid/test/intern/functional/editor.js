define([
	"intern!tdd",
	"intern/chai!assert",
	"./util",
	"dojo/node!wd/lib/special-keys",
	"require"
], function (test, assert, util, specialKeys, require) {
	// Number of visible rows in the grid.
	// Check the data loaded in test file (editor.html) and rows visible
	// when the page is loaded to ensure this is correct.
	var GRID_ROW_COUNT = 3;
	var rowSelectorPrefix = "#grid-row-";

	test.suite("dgrid/editor functional tests", function () {
		var gotoEnd; // Function defined when `before` logic runs
		
		// Functions to dismiss field and register edited value, passed to createDatachangeTest

		function dismissViaEnter(remote) {
			return remote.type(specialKeys.Enter)
				.end();
		}

		function dismissViaBlur(remote) {
			return remote.end()
				.elementByTagName("h2")
				.click()
				.end();
		}

		// Functions performing operations to test the editor columns in the grid,
		// passed to createDatachangeTest

		function testAlwaysOnEditor(remote, rowIndex, dismissFunc) {
			var startValue,
				appendValue = "abc";

			// Click the cell's editor element to focus it
			remote.elementByCssSelector(rowSelectorPrefix + rowIndex + " .field-name input")
					.clickElement()

					// Store the current cell value
					.getValue()
					.then(function (cellValue) {
						startValue = cellValue;
					});

				// Type extra chars to change value
				gotoEnd(remote)
					.type(appendValue);
				dismissFunc(remote); // calls end

			// Click another cell to blur the edited cell (and trigger saving and dgrid-datachange event)
			remote.elementByCssSelector(rowSelectorPrefix + rowIndex + " .field-description")
				.clickElement()
				// The test page has a dgrid-datachange event listener that will push the new value
				// into a global array: datachangeStack
				.execute("return datachangeStack.shift();")
				.then(function (datachangeValue) {
					assert.strictEqual(startValue + appendValue, datachangeValue,
						"Value in dgrid-datachange event (" + datachangeValue +
							") should equal edited value (" + startValue + appendValue + ")");
				})
				.end();
		}

		function testEditOnEditor(remote, rowIndex, dismissFunc) {
			var cellSelector = rowSelectorPrefix + rowIndex + " .field-description",
				startValue,
				appendValue = "abc";

			// Click the cell to activate the editor
			remote.elementByCssSelector(cellSelector)
					.clickElement()
					.end()
				// Set context to the cell's editor
				.elementByCssSelector(cellSelector + " input")
					// Store the current cell value
					.getValue()
					.then(function (cellValue) {
						startValue = cellValue;
					});

				// Type extra chars to change value
				gotoEnd(remote)
					.type(appendValue);
				dismissFunc(remote); // calls end

			// The test page has a dgrid-datachange event listener that will push the new value
			// into a global array: datachangeStack
			remote.execute("return datachangeStack.shift();")
				.then(function (datachangeValue) {
					assert.strictEqual(startValue + appendValue, datachangeValue,
						"Value in dgrid-datachange event (" + datachangeValue +
							") should equal edited value (" + startValue + appendValue + ")");
				});
		}

		function createDatachangeTest(testFunc, dismissFunc, initFunction) {
			// Generates test functions for enter/blur value registration tests
			return function () {
				this.async(60000);
				var remote = this.get("remote");

				remote.get(require.toUrl("./editor.html"));
				remote.waitForCondition("ready", 15000);

				if (initFunction) {
					remote.execute(initFunction);
				}

				for (var rowIndex = 0; rowIndex < GRID_ROW_COUNT; rowIndex++) {
					testFunc(remote, rowIndex, dismissFunc);
				}
				
				return remote.end();
			};
		}

		function createFocusTest(selector, initFunction) {
			// Generates test functions for focus preservation tests
			return function () {
				var remote = this.get("remote"),
					rowIndex;

				function each(rowIndex) {
					// Click the cell to activate and focus the editor
					remote.elementByCssSelector(rowSelectorPrefix + rowIndex + " " + selector)
							.clickElement()
							.end()
						.executeAsync(function (id, rowIdPrefix, done) {
							/* global grid */
							function getRowId(node) {
								// Retrieves ID of row based on an input node
								while (node && node.id.slice(0, 9) !== rowIdPrefix) {
									node = node.parentNode;
								}
								return node && node.id;
							}

							var activeId = getRowId(document.activeElement);
							grid.store.notify(grid.store.get(id), id);
							// Need to wait until next turn for refocus
							setTimeout(function () {
								done(activeId === getRowId(document.activeElement));
							}, 0);
						}, [ rowIndex, rowSelectorPrefix.slice(1) ])
						.then(function (testPassed) {
							assert.isTrue(testPassed,
								"Focused element before refresh should remain focused after refresh");
						})
						.elementByTagName("h2")
							.click()
							.end();
				}

				remote.get(require.toUrl("./editor-OnDemand.html"))
					.waitForCondition("ready", 15000);

				if (initFunction) {
					remote.execute(initFunction);
				}

				for (rowIndex = 0; rowIndex < GRID_ROW_COUNT; rowIndex++) {
					each(rowIndex);
				}

				return remote.end();
			};
		}

		function createEscapeRevertTest(initFunction) {
			return function () {
				var remote = this.get("remote"),
					rowIndex;

				function each(rowIndex) {
					var cellSelector = rowSelectorPrefix + rowIndex + " .field-description",
						startValue,
						appendValue = "abc";

					// Click the cell to focus the editor
					remote.elementByCssSelector(cellSelector)
							.clickElement()
							.end()
						// Get the initial value from the editor field
						.elementByCssSelector(cellSelector + " input")
							.getValue()
							.then(function (cellValue) {
								startValue = cellValue;
							});

						// Append extra chars and verify the editor's value has updated
						gotoEnd(remote)
							.type(appendValue)
							.getValue()
							.then(function (cellValue) {
								assert.notStrictEqual(startValue, cellValue,
									"Row " + rowIndex + " editor value should differ from the original");
							})
							// Send Escape and verify the value has reverted in the grid's data
							.type(specialKeys.Escape)
							.execute("return grid.row(" + rowIndex + ").data.description;")
							.then(function (cellValue) {
								assert.strictEqual(startValue, cellValue,
									"Row " + rowIndex + " editor value should equal the starting value after escape");
							})
							.end();
				}

				remote.get(require.toUrl("./editor.html"))
					.waitForCondition("ready", 15000);

				if (initFunction) {
					remote.execute(initFunction);
				}

				for (rowIndex = 0; rowIndex < GRID_ROW_COUNT; rowIndex++) {
					each(rowIndex);
				}

				return remote.end();
			};
		}

		function createAutosaveTest(initFunction) {
			return function () {
				var remote = this.get("remote"),
					appendValue = "abc",
					rowIndex;

				function each(rowIndex) {
					var editedValue;

					// Click the cell editor and update the value
					remote.elementByCssSelector(rowSelectorPrefix + rowIndex + " .field-name input")
							.clickElement();
						gotoEnd(remote)
							.type(appendValue)
							.getValue()
							.then(function (cellValue) {
								editedValue = cellValue;
							});
						dismissViaBlur(remote); // calls end

					// Click elsewhere to trigger saving of edited cell
					remote.elementByTagName("h2")
							.clickElement()
						.end()
						// Wait for the save to complete before moving on to next iteration
						.waitForCondition("saveComplete", 5000)
						// Get the saved value from the test page and verify it
						.execute("return gridSaveStack.shift();")
						.then(function (savedValue) {
							assert.strictEqual(editedValue, savedValue,
								"Row " + rowIndex + ", column 'name' saved value (" + savedValue +
									") should equal the entered value (" + editedValue + ")");
						});
				}

				remote.get(require.toUrl("./editor-OnDemand.html"))
					.waitForCondition("ready", 15000);

				if (initFunction) {
					remote.execute(initFunction);
				}

				for (rowIndex = 0; rowIndex < GRID_ROW_COUNT; rowIndex++) {
					each(rowIndex);
				}

				return remote.end();
			};
		}

		// Function passed to above functions to change grid column structure
		// to test other types of editors
		
		function setTextBox() {
			/* global setEditorToTextBox */
			setEditorToTextBox();
		}
		
		test.before(function () {
			// In order to function properly on all platforms, we need to know
			// what the proper character sequence is to go to the end of a text field.
			// End key works generally everywhere except Mac OS X.
			return util.isInputHomeEndSupported(this.get("remote")).then(function (isSupported) {
				gotoEnd = isSupported ? function (remote) {
					return remote.type(specialKeys.End);
				} : function (remote) {
					return remote.keys(specialKeys.Meta + specialKeys["Right arrow"] +
						specialKeys.NULL);
				};
			});
		});

		test.test("escape reverts edited value", createEscapeRevertTest());
		test.test("escape reverts edited value - TextBox", createEscapeRevertTest(setTextBox));

		// This combination works, though it's debatable whether it even should
		test.test("enter registers edited value for always-on editor",
			createDatachangeTest(testAlwaysOnEditor, dismissViaEnter));

		test.test("enter registers edited value for editOn editor",
			createDatachangeTest(testEditOnEditor, dismissViaEnter));

		test.test("blur registers edited value for always-on editor",
			createDatachangeTest(testAlwaysOnEditor, dismissViaBlur));

		test.test("blur registers edited value for always-on editor - TextBox",
			createDatachangeTest(testAlwaysOnEditor, dismissViaBlur, setTextBox));

		test.test("blur registers edited value for editOn editor",
			createDatachangeTest(testEditOnEditor, dismissViaBlur));

		test.test("blur registers edited value for editOn editor - TextBox",
			createDatachangeTest(testEditOnEditor, dismissViaBlur, setTextBox));

		test.test("maintain focus on update for always-on editor",
			createFocusTest(".field-name input"));

		test.test("maintain focus on update for always-on editor - TextBox",
			createFocusTest(".field-name input", setTextBox));

		test.test("maintain focus on update for editOn editor",
			createFocusTest(".field-description"));

		test.test("maintain focus on update for editOn editor - TextBox",
			createFocusTest(".field-description", setTextBox));

		test.test("autoSave: true", createAutosaveTest());
		test.test("autoSave: true - TextBox", createAutosaveTest(setTextBox));
	});
});
