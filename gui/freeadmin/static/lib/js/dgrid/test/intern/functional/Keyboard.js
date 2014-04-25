define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/node!wd/lib/special-keys",
	"require"
], function(test, assert, specialKeys, require){
	function testUpDownKeys(gridId, cellNavigation){
		var rootQuery = "#" + gridId + " #" + gridId + "-row-";
		return function(){
			return this.get("remote")
				.elementByCssSelector(rootQuery + "0" + (cellNavigation ? " .dgrid-column-col1" : ""))
					.clickElement()
					.type([specialKeys["Down arrow"]])
					.end()
				.elementByCssSelector(rootQuery + "1" + (cellNavigation ? " .dgrid-column-col1" : ""))
					.getAttribute("class")
					.then(function(classNames){
						var arr = classNames.split(" "),
							containsClass = (arr.indexOf("dgrid-focus") !== -1);
						assert.ok(containsClass, "the down arrow key should move focus one element down");
					})
					.type([specialKeys["Up arrow"]])
					.end()
				.elementByCssSelector(rootQuery + "0" + (cellNavigation ? " .dgrid-column-col1" : ""))
					.getAttribute("class")
					.then(function(classNames){
						var arr = classNames.split(" "),
							containsClass = (arr.indexOf("dgrid-focus") !== -1);
						assert.ok(containsClass, "the up arrow key should move focus one element up");
					})
					.end();
		};
	}

	function testLeftRightKeys(gridId, header){
		var rootQuery = header ? ("#" + gridId + " .dgrid-header") : ("#" + gridId + " #" + gridId + "-row-0");
		return function(){
			return this.get("remote")
				.elementByCssSelector(rootQuery + " .dgrid-column-col1")
					.clickElement()
					.type([specialKeys["Right arrow"]])
					.end()
				.elementByCssSelector(rootQuery + " .dgrid-column-col2")
					.getAttribute("class")
					.then(function(classNames){
						var arr = classNames.split(" "),
							containsClass = (arr.indexOf("dgrid-focus") !== -1);
						assert.ok(containsClass, "the right arrow key should move focus one element right");
					})
					.type([specialKeys["Left arrow"]])
					.end()
				.elementByCssSelector(rootQuery + " .dgrid-column-col1")
					.getAttribute("class")
					.then(function(classNames){
						var arr = classNames.split(" "),
							containsClass = (arr.indexOf("dgrid-focus") !== -1);
						assert.ok(containsClass, "the left arrow key should move focus one element left");
					})
					.end();
		};
	}

	function testHomeEndKeys(gridId, cellNavigation, onDemand){
		var rootQuery = "#" + gridId + " #" + gridId + "-row-";
		return function(){
			return this.get("remote")
				.elementByCssSelector(rootQuery + "0" + (cellNavigation ? " .dgrid-column-col1" : ""))
					.clickElement()
					.type([specialKeys.End])
					.end()
				.setImplicitWaitTimeout(1000)
				// Note that this assumes the list is always 100 items, 0-99
				.elementByCssSelector("#" + gridId + "-row-99" + (cellNavigation ? " .dgrid-column-col1" : ""))
					.getAttribute("class")
					.then(function(classNames){
						var arr = classNames.split(" "),
						containsClass = arr.indexOf("dgrid-focus") !== -1;
						assert.ok(containsClass, "the end key should move focus to the last element in the list");
					})
					.type([specialKeys.Home])
					.end()
				.elementByCssSelector(rootQuery + "0" + (cellNavigation ? " .dgrid-column-col1" : ""))
					.getAttribute("class")
					.then(function(classNames){
						var arr = classNames.split(" "),
							containsClass = (arr.indexOf("dgrid-focus") !== -1);
						assert.ok(containsClass, "the home key should move focus to the first element in the list");
					})
					.end();
		};
	}

	test.suite("Keyboard functional tests", function(){
		test.before(function(){
			// Get our html page. This page should load all necessary scripts
			// since this functional test module runs on the server and can't load
			// such scripts. Further, in the html page, set a global "ready" var
			// to true to tell the runner to continue.
			return this.get("remote")
				.get(require.toUrl("./Keyboard.html"))
				.waitForCondition("ready", 5000);
		});
		
		test.test("grid (cellNavigation: true) -> up + down arrow keys",
			testUpDownKeys("grid", true));

		test.test("grid (cellNavigation: false) -> up + down arrow keys",
			testUpDownKeys("rowGrid"));

		test.test("list -> up + down arrow keys",
			testUpDownKeys("list"));

		test.test("grid row -> left + right arrow keys",
			testLeftRightKeys("grid"));

		test.test("grid header -> left + right arrow keys",
			testUpDownKeys("grid", true));

		test.test("simple grid (cellNavigation: true) -> home + end keys",
			testHomeEndKeys("grid", true));

		test.test("simple grid (cellNavigation: false) -> home + end keys",
			testHomeEndKeys("rowGrid"));

		test.test("simple list -> home + end keys",
			testHomeEndKeys("list"));

		test.test("on-demand grid (cellNavigation: true) -> home + end keys",
			testHomeEndKeys("grid-ondemand", true, true));

		test.test("on-demand simple grid (cellNavigation: false) -> home + end keys",
			testHomeEndKeys("rowGrid-ondemand", false, true));

		test.test("on-demand simple list -> home + end keys",
			testHomeEndKeys("list-ondemand", false, true));
	});
});