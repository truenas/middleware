define([
	"intern!tdd",
	"intern/chai!assert",
	"dojo/node!wd/lib/special-keys",
	"require"
], function(test, assert, specialKeys, require){
	var tabKey = specialKeys.Tab;
	test.suite("Keyboard tab key functional tests", function(){
		test.before(function(){
			// Get our html page. This page should load all necessary scripts
			// since this functional test module runs on the server and can't load
			// such scripts. Further, in the html page, set a global "ready" var
			// to true to tell the runner to continue.
			return this.get("remote")
				.get(require.toUrl("./KeyboardTab.html"))
				.waitForCondition("ready", 5000);
		});

		test.test("grids with and without headers -> tab key", function(){
			return this.get("remote")
				.active()
					.getAttribute("id")
					.then(function(id){
						assert.strictEqual(id, "showHeaderButton", "Focus is on the button: " + id);
					})
				.type(tabKey)
				.active()
					.getAttribute("role").then(function(role){
						assert.strictEqual(role, "columnheader", "Focus is on a column header: " + role);
					})
				.type(tabKey)
				.active()
					.getAttribute("role").then(function(role){
						assert.strictEqual(role, "gridcell", "Focus is on a grid cell: " + role);
					})
					.text().then(function(text){
						assert.strictEqual(text, "0", "The cell with focus contains 0: " + text);
					})
				.type(tabKey)
				.active()
					.getAttribute("role").then(function(role){
						assert.strictEqual(role, "gridcell", "Focus is on a grid cell: " + role);
					})
					.text().then(function(text){
						assert.strictEqual(text, "10", "The cell with focus contains 10: " + text);
					})
					.reset()
				.elementById("showHeaderButton")
					.click()
				.active()
					.getAttribute("id")
					.then(function(id){
						assert.strictEqual(id, "showHeaderButton", "Focus is on the button: " + id);
					})
				.type(tabKey)
				.active()
					.getAttribute("role").then(function(role){
						assert.strictEqual(role, "columnheader", "Focus is on a column header: " + role);
					})
				.type(tabKey)
				.active()
					.getAttribute("role").then(function(role){
						assert.strictEqual(role, "gridcell", "Focus is on a grid cell: " + role);
					})
					.text().then(function(text){
						assert.strictEqual(text, "0", "The cell with focus contains 0: " + text);
					})
				.type(tabKey)
				.active()
					.getAttribute("role").then(function(role){
						assert.strictEqual(role, "columnheader", "Focus is on a column header: " + role);
					})
				.type(tabKey)
				.active()
					.getAttribute("role").then(function(role){
						assert.strictEqual(role, "gridcell", "Focus is on a grid cell: " + role);
					})
					.text().then(function(text){
						assert.strictEqual(text, "10", "The cell with focus contains 10: " + text);
					});
		});
	});
});