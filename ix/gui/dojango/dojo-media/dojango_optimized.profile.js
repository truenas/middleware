dependencies = {
	layers: [
		{
			name: "dojo.js",
			layerDependencies: [
				"../dijit/dijit.js"
			],
			dependencies: [
				"dojango.dojango",
				"dojo.dnd.Source",
				"dojo.parser",
				"dojo.date.locale",
				"dojo.data.ItemFileReadStore",
				"dojox.data.QueryReadStore",
				"dijit.dijit-all",
				"dijit.form.TimeTextBox"
			]
		}
	],
	
	prefixes: [
		[ "dijit", "../dijit" ],
		[ "dojox", "../dojox" ],
		[ "dojango", "../../../dojango" ] // relative to the directory, where the dojo.js source file resides
	]
}