define([
	"intern!object",
	"intern/chai!assert",
	"require"
], function(test, assert, require){
	var keys = {
			up: "\uE013",
			down: "\uE015",
			left: "\uE012",
			right: "\uE014",
			home: "\uE011",
			end: "\uE010"
		},

		testUpDownKeys = function(gridId, cellNavigation){
			var rootQuery = "#" + gridId + " #" + gridId + "-row-";
			return function(){
				return this.get("remote")
					.elementByCssSelector(rootQuery + "0" + (cellNavigation ? " .dgrid-column-col1" : ""))
						.clickElement()
						.type([keys.down])
						.end()
					.elementByCssSelector(rootQuery + "1" + (cellNavigation ? " .dgrid-column-col1" : ""))
						.getAttribute("class")
						.then(function(classNames){
							var arr = classNames.split(" "),
								containsClass = (arr.indexOf("dgrid-focus") !== -1);
							assert.ok(containsClass, "the down arrow key should move focus one element down");
						})
						.type([keys.up])
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
		},

		testLeftRightKeys = function(gridId, header){
			var rootQuery = header ? ("#" + gridId + " .dgrid-header") : ("#" + gridId + " #" + gridId + "-row-0");
			return function(){
				return this.get("remote")
					.elementByCssSelector(rootQuery + " .dgrid-column-col1")
						.clickElement()
						.type([keys.right])
						.end()
					.elementByCssSelector(rootQuery + " .dgrid-column-col2")
						.getAttribute("class")
						.then(function(classNames){
							var arr = classNames.split(" "),
								containsClass = (arr.indexOf("dgrid-focus") !== -1);
							assert.ok(containsClass, "the right arrow key should move focus one element right");
						})
						.type([keys.left])
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
		},

		testHomeEndKeys = function(gridId, cellNavigation, onDemand){
			var rootQuery = "#" + gridId + " #" + gridId + "-row-";
			return function(){
				return this.get("remote")
					.elementByCssSelector(rootQuery + "0" + (cellNavigation ? " .dgrid-column-col1" : ""))
						.clickElement()
						.type([keys.end])
						.end()
					.elementByCssSelector("#" + gridId + " .dgrid-content>" + (onDemand ? ":nth-last-child(2)" : ":last-child") + (cellNavigation ? " .dgrid-column-col1" : ""))
						.getAttribute("class")
						.then(function(classNames){
							var arr = classNames.split(" "),
								containsClass;
							if(onDemand){
								//TODO we should check for the class with the right store item id...
								containsClass = (arr.indexOf("dgrid-focus") !== -1);
								assert.ok(containsClass, "the end key should move focus to the last element in the list");
							}else{
								containsClass = (arr.indexOf("dgrid-focus") !== -1);
								assert.ok(containsClass, "the end key should move focus to the last element in the list");
							}
						})
						.type([keys.home])
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
		};

	return test({
		before: function(){
			// Get our html page. This page should load all necessary scripts
			// since this functional test module runs on the server and can't load
			// such scripts. Further, in the html page, set a global "ready" var
			// to true to tell the runner to continue.
			return this.get("remote")
				.get(require.toUrl("./Keyboard.html"))
				.waitForCondition("ready", 5000);
		},

		"grid (cellNavigation: true) -> up + down arrow keys" : testUpDownKeys("grid", true),

		"grid (cellNavigation: false) -> up + down arrow keys" : testUpDownKeys("rowGrid"),

		"list -> up + down arrow keys" : testUpDownKeys("list"),

		"grid row -> left + right arrow keys" : testLeftRightKeys("grid"),

		"grid header -> left + right arrow keys" : testUpDownKeys("grid", true),

		"simple grid (cellNavigation: true) -> home + end keys" : testHomeEndKeys("grid", true),

		"simple grid (cellNavigation: false) -> home + end keys" : testHomeEndKeys("rowGrid"),

		"simple list -> home + end keys" : testHomeEndKeys("list"),

		"on-demand grid (cellNavigation: true) -> home + end keys" : testHomeEndKeys("grid-ondemand", true, true),

		"on-demand simple grid (cellNavigation: false) -> home + end keys" : testHomeEndKeys("rowGrid-ondemand", false, true),

		"on-demand simple list -> home + end keys" : testHomeEndKeys("list-ondemand", false, true)
	});
});